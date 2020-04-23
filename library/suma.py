#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020- IBM, Inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
author:
- AIX Development Team (@pbfinley1911)
module: suma
short_description: Download/Install fixes, SP or TL on an AIX server.
description:
- Creates a task to automate the download and installation of technology level (TL)
  and service packs (SP) from a fix server using the Service Update Management
  Assistant (SUMA). Log file is /var/adm/ansible/suma_debug.log.
version_added: '2.9'
requirements:
- AIX >= 7.1 TL3
- Python >= 2.7
options:
  action:
    description:
    - Controls the action to be performed.
    - C(download) to download and install all fixes.
    - C(preview) to execute all the checks without downloading the fixes.
    - C(list) to list all SUMA tasks.
    - C(edit) to edit an exiting SUMA task.
    - C(unschedule) to remove any scheduling information for the specified SUMA task.
    - C(delete) to delete a SUMA task and remove any schedules for this task.
    - C(config) to list global SUMA configuration settings.
    - C(default) to list default SUMA tasks.
    type: str
    choices: [ download, preview, list, edit, unschedule, delete, config, default ]
    default: download
  oslevel:
    description:
    - Specifies the Operating System level to update to;
    - C(Latest) indicates the latest SP suma can update the target to (for the current TL).
    - C(xxxx-xx(-00-0000)) sepcifies a TL.
    - C(xxxx-xx-xx-xxxx) or C(xxxx-xx-xx) specifies a SP.
    - Required when I(action=download) or I(action=preview).
    type: str
    default: Latest
  download_dir:
    description:
    - Directory where updates are downloaded.
    - Can be used if I(action=download) or C(action=preview).
    type: path
    default: /usr/sys/inst.images
  download_only:
    description:
    - Download only. Do not perform installation of updates.
    - Can be used if I(action=download) or C(action=preview).
    type: bool
    default: no
  last_sp:
    description:
    - Specifies to download the last SP of the TL specified in I(oslevel). If no is specified only the TL is downloaded.
    - Can be used if I(action=download) or C(action=preview).
    type: bool
    default: no
  extend_fs:
    description:
    - Specifies to automatically extends the filesystem if needed. If no is specified and additional space is required for the download, no download occurs.
    - Can be used if I(action=download) or C(action=preview).
    type: bool
    default: yes
  task_id:
    description:
    - SUMA task identification number.
    - Can be used if I(action=list) or I(action=edit) or I(action=delete) or I(action=unschedule).
    - Required when I(action=edit) or I(action=delete) or I(action=unschedule).
    type: str
  sched_time:
    description:
    - Schedule time. Specifying an empty or space filled string results in unscheduling the task. If not set, it saves the task.
    - Can be used if I(action=edit).
    type: str
  description:
    description:
    - Display name for SUMA task.
    - If not set the will be labelled 'I(action) request for oslevel I(oslevel)'
    type: str
  metadata_dir:
    description:
    - Directory where metadata files are downloaded.
    - Can be used if I(action=download) or C(action=preview) when I(last_sp=yes) or I(oslevel) is not exact, for example I(oslevel=Latest).
    type: path
    default: /var/adm/ansible/metadata
'''

EXAMPLES = r'''
- name: Check, download and install system updates for the current oslevel of the system
  suma:
    oslevel: Latest
    download_dir: /usr/sys/inst.images

- name: Check and download required to update to SP 7.2.3.2
  suma:
    oslevel: '7200-03-02'
    download_only: yes
    download_dir: /tmp/dl_updt_7200-03-02
  when: ansible_distribution == 'AIX'

- name: Check, download and install to latest SP of TL 7.2.4
  suma:
    oslevel: '7200-04'
    last_sp: yes
    extend_fs: no

- name: Check, download and install to TL 7.2.3
  suma:
    oslevel: '7200-03'
'''

RETURN = r'''
meta:
    description: Detailed information on the module execution.
    returned: always
    type: dict
    contains:
        messages:
            description: Details on errors/warnings/inforamtion
            returned: always
            type: list
            elements: str
            sample: "Parameter last_sp={} is ignored when oslevel is a TL 7200-02-00"
    sample:
        "meta": {
            "messages": [
                "Parameter last_sp=yes is ignored when oslevel is a TL ",
                "Suma metadata: 7200-02-01-1732 is the latest SP of TL 7200-02",
                ...,
            ]
        }
'''

import os
import re
import glob
import shutil
import logging

from ansible.module_utils.basic import AnsibleModule

module = None
results = None
suma_params = {}
logdir = "/var/adm/ansible"


def logged(func):
    """
    Decorator for logging
    """
    def logged_wrapper(*args):
        """
        Decorator wrapper for logging
        """
        logging.debug('ENTER {} with {}'.format(func.__name__, args))
        res = func(*args)
        logging.debug('EXIT {} with {}'.format(func.__name__, res))
        return res
    return logged_wrapper


@logged
def compute_rq_type(oslevel, last_sp):
    """
    Compute rq_type to use in a suma request based on provided oslevel.
    arguments:
        oslevel level of the OS
        last_sp boolean specifying if we should get the last SP
    return:
        Latest when oslevel is blank or latest (not case sensitive)
        SP     when oslevel is a TL (6 digits: xxxx-xx) and last_sp==True
        TL     when oslevel is xxxx-xx(-00-0000)
        SP     when oslevel is xxxx-xx-xx(-xxxx)
        ERROR  when oslevel is not recognized
    """
    global results

    if oslevel is None or not oslevel.strip() or oslevel == 'Latest':
        return 'Latest'
    if re.match(r"^([0-9]{4}-[0-9]{2})$", oslevel) and last_sp:
        return 'SP'
    if re.match(r"^([0-9]{4}-[0-9]{2})(|-00|-00-0000)$", oslevel):
        if last_sp:
            msg = "Parameter last_sp={} is ignored when oslevel is a TL {}.".format(last_sp, oslevel)
            logging.info(msg)
            results['meta']['messages'].append(msg)
        return 'TL'
    if re.match(r"^([0-9]{4}-[0-9]{2}-[0-9]{2})(|-[0-9]{4})$", oslevel):
        return 'SP'

    return 'ERROR'


@logged
def find_sp_version(file):
    """
    Open and parse the provided file to find higher SP version
    arguments:
        file    path of the file to parse
    return:
       sp_version   value found or None
    """
    sp_version = None
    logging.debug("opening file: {}".format(file))
    myfile = open(file, "r")
    for line in myfile:
        # logging.debug("line: {}".format(line.rstrip()))
        match_item = re.match(
            r"^<SP name=\"([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4})\">$",
            line.rstrip())
        if match_item:
            version = match_item.group(1)
            logging.debug("matched line: {}, version={}".format(line.rstrip(), version))
            if sp_version is None or version > sp_version:
                sp_version = version
            break
    myfile.close()

    return sp_version


@logged
def compute_rq_name(rq_type, oslevel, last_sp):
    """
    Compute rq_name.
        if oslevel is a TL then return the SP extratced from it
        if oslevel is a complete SP (12 digits) then return RqName = oslevel
        if oslevel is an incomplete SP (8 digits) or equal Latest then execute
        a metadata suma request to find the complete SP level (12 digits).
    The return format depends on rq_type value,
        - for Latest: return a SP value in the form xxxx-xx-xx-xxxx
        - for TL: return the TL value in the form xxxx-xx
        - for SP: return the SP value in the form xxxx-xx-xx-xxxx

    arguments:
        rq_type     type of request, can be Latest, SP or TL
        oslevel     requested oslevel
        last_sp     if set get the latest SP level for specified oslevel
    note:
        Exits with fail_json in case of error
    return:
       rq_name value
    """
    global results
    global suma_params

    rq_name = ''
    if rq_type == 'TL':
        rq_name = re.match(r"^([0-9]{4}-[0-9]{2})(|-00|-00-0000)$",
                           oslevel).group(1)

    elif rq_type == 'SP' and re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4}$", oslevel):
        rq_name = oslevel

    else:
        if oslevel == 'Latest':
            # Get the current oslevel of the system
            cmd = ['/bin/oslevel', '-s']

            rc, stdout, stderr = module.run_command(cmd)
            if rc != 0:
                msg = "Suma oslevel command '{}' failed with return code {}".format(' '.join(cmd), rc)
                logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
                results['stdout'] = stdout
                results['stderr'] = stderr
                results['msg'] = msg
                module.fail_json(**results)
            elif not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(|-[0-9]{2}|-[0-9]{4})$", stdout.strip()):
                msg = "Suma oslevel command '{}' returned an unexpected OS level '{}'".format(' '.join(cmd), stdout)
                logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
                results['stdout'] = stdout
                results['stderr'] = stderr
                results['msg'] = msg
                module.fail_json(**results)
            logging.debug("SUMA command '{}' rc:{}, stdout:{}".format(' '.join(cmd), rc, stdout))
            oslevel = stdout.strip()
            rq_oslevel = oslevel[:7]
        else:
            rq_oslevel = oslevel

        # rq_oslevel has either a TL format (xxxx-xx) or a short SP format (xxxx-xx-xx)

        # Build the FilterML for metadata request from the rq_oslevel
        metadata_filter_ml = rq_oslevel[:7]
        if not metadata_filter_ml:
            msg = "Cannot build minimum level filter based on the target OS level {}".format(oslevel)
            logging.error(msg)
            results['msg'] = msg
            module.fail_json(**results)

        if not os.path.exists(suma_params['metadata_dir']):
            os.makedirs(suma_params['metadata_dir'])

        # Build suma command to get metadata
        cmd = ['/usr/sbin/suma', '-x', '-a', 'Action=Metadata', '-a', 'RqType=Latest']
        cmd += ['-a', 'DLTarget={}'.format(suma_params['metadata_dir'])]
        cmd += ['-a', 'FilterML={}'.format(metadata_filter_ml)]
        cmd += ['-a', 'DisplayName="{}"'.format(suma_params['description'])]
        cmd += ['-a', 'FilterDir={}'.format(suma_params['metadata_dir'])]

        rc, stdout, stderr = module.run_command(cmd)
        if rc != 0:
            msg = "Suma metadata command '{}' failed with return code {}".format(' '.join(cmd), rc)
            logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
            results['stdout'] = stdout
            results['stderr'] = stderr
            results['msg'] = msg
            module.fail_json(**results)
        logging.debug("SUMA command '{}' rc:{}, stdout:{}".format(' '.join(cmd), rc, stdout))

        sp_version = None
        if len(rq_oslevel) == 10:
            # find latest SP build number for the SP
            file_name = suma_params['metadata_dir'] + "/installp/ppc/" + rq_oslevel + ".xml"
            sp_version = find_sp_version(file_name)
        else:
            # find latest SP build number for the TL
            file_name = suma_params['metadata_dir'] + "/installp/ppc/" + "*.xml"
            files = glob.glob(file_name)
            logging.debug("searching SP in files: {}".format(files))
            for cur_file in files:
                version = find_sp_version(cur_file)
                if sp_version is None or version > sp_version:
                    sp_version = version

        if sp_version is None or not sp_version.strip():
            msg = "Cannot determine SP version for OS level {}: 'SP name' not found in metadata files {}".format(oslevel, files)
            logging.error(msg)
            results['msg'] = msg
            module.fail_json(**results)

        shutil.rmtree(suma_params['metadata_dir'])

        rq_name = sp_version
        msg = 'Suma metadata: {} is the latest SP of {}'.format(rq_name, oslevel)
        logging.info(msg)
        results['meta']['messages'].append(msg)

    if not rq_name or not rq_name.strip():  # should never happen
        msg = "OS level {} does not match any fixes".format(oslevel)
        logging.error(msg)
        results['msg'] = msg
        module.fail_json(**results)

    return rq_name


@logged
def suma_command(action):
    """
    Run a suma command.

    arguments:
        action   preview, download or install
    note:
        Exits with fail_json in case of error
    return:
       rc      suma command return code
       stdout  suma command output
    """
    global results

    rq_type = suma_params['RqType']
    cmd = ['/usr/sbin/suma', '-x', '-a', 'RqType={}'.format(rq_type)]
    cmd += ['-a', 'Action={}'.format(action)]
    cmd += ['-a', 'DLTarget={}'.format(suma_params['DLTarget'])]
    cmd += ['-a', 'DisplayName={}'.format(suma_params['description'])]

    if rq_type != 'Latest':
        cmd += ['-a', 'RqName={}'.format(suma_params['RqName'])]

    if suma_params['extend_fs']:
        cmd += ['-a', 'Extend=y']
    else:
        cmd += ['-a', 'Extend=n']

    logging.debug("SUMA - Command:{}".format(' '.join(cmd)))
    results['meta']['messages'].append("SUMA - Command: {}".format(' '.join(cmd)))

    rc, stdout, stderr = module.run_command(cmd)
    results['stdout'] = stdout
    results['stderr'] = stderr
    if rc != 0:
        msg = "Suma {} command '{}' failed with return code {}".format(action, ' '.join(cmd), rc)
        logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
        results['msg'] = msg
        module.fail_json(**results)

    return rc, stdout


@logged
def suma_list():
    """
    List all SUMA tasks or the task associated with the given task ID

    note:
        Exits with fail_json in case of error
    """
    global results

    task = suma_params['task_id']
    if task is None or not task.strip():
        task = ''

    cmd = ['/usr/sbin/suma', '-l', task]
    rc, stdout, stderr = module.run_command(cmd)

    results['stdout'] = stdout
    results['stderr'] = stderr

    if rc != 0:
        msg = "Suma list command '{}' failed with return code {}".format(' '.join(cmd), rc)
        logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
        results['msg'] = msg
        module.fail_json(**results)


@logged
def check_time(val, mini, maxi):
    """
    Check a value is equal to '*' or is a numeric value in the
    [mini, maxi] range

    arguments:
        val     value to check
        mini    range minimal value
        mini    range maximal value
    """
    if val == '*':
        return True

    if val.isdigit() and mini <= int(val) and maxi >= int(val):
        return True

    return False


@logged
def suma_edit():
    """
    Edit a SUMA task associated with the given task ID

    Depending on the shed_time parameter value, the task wil be scheduled,
        unscheduled or saved

    note:
        Exits with fail_json in case of error
    """
    global results

    cmd = '/usr/sbin/suma'
    if suma_params['sched_time'] is None:
        # save
        cmd += ' -w'

    elif not suma_params['sched_time'].strip():
        # unschedule
        cmd += ' -u'

    else:
        # schedule
        minute, hour, day, month, weekday = suma_params['sched_time'].split(' ')

        if check_time(minute, 0, 59) and check_time(hour, 0, 23) \
           and check_time(day, 1, 31) and check_time(month, 1, 12) \
           and check_time(weekday, 0, 6):

            cmd += ' -s "{}"'.format(suma_params['sched_time'])
        else:
            msg = "Suma edit command '{}' failed Bad schedule time '{}'".format(' '.join(cmd), suma_params['sched_time'])
            logging.error(msg)
            results['msg'] = msg
            module.fail_json(**results)

    cmd += ' {}'.format(suma_params['task_id'])
    rc, stdout, stderr = module.run_command(cmd)

    results['stdout'] = stdout
    results['stderr'] = stderr

    if rc != 0:
        msg = "Suma edit command '{}' failed with return code {}".format(cmd, rc)
        logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
        results['msg'] = msg
        module.fail_json(**results)


@logged
def suma_unschedule():
    """
    Unschedule a SUMA task associated with the given task ID

    note:
        Exits with fail_json in case of error
    """
    global results

    cmd = "/usr/sbin/suma -u {}".format(suma_params['task_id'])
    rc, stdout, stderr = module.run_command(cmd)

    results['stdout'] = stdout
    results['stderr'] = stderr

    if rc != 0:
        msg = "Suma unschedule command '{}' failed with return code {}".format(cmd, rc)
        logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
        results['msg'] = msg
        module.fail_json(**results)


@logged
def suma_delete():
    """
    Delete the SUMA task associated with the given task ID

    note:
        Exits with fail_json in case of error
    """
    global results

    cmd = "/usr/sbin/suma -d {}".format(suma_params['task_id'])
    rc, stdout, stderr = module.run_command(cmd)

    results['stdout'] = stdout
    results['stderr'] = stderr

    if rc != 0:
        msg = "Suma delete command '{}' failed with return code {}".format(cmd, rc)
        logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
        results['msg'] = msg
        module.fail_json(**results)


@logged
def suma_config():
    """
    List the SUMA global configuration settings

    note:
        Exits with fail_json in case of error
    """
    global results

    cmd = '/usr/sbin/suma -c'
    rc, stdout, stderr = module.run_command(cmd)

    results['stdout'] = stdout
    results['stderr'] = stderr

    if rc != 0:
        msg = "Suma config command '{}' failed with return code {}".format(cmd, rc)
        logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
        results['msg'] = msg
        module.fail_json(**results)


@logged
def suma_default():
    """
    List default SUMA tasks

    note:
        Exits with fail_json in case of error
    """
    global results

    cmd = '/usr/sbin/suma -D'
    rc, stdout, stderr = module.run_command(cmd)

    results['stdout'] = stdout
    results['stderr'] = stderr

    if rc != 0:
        msg = "Suma list default command '{}' failed with return code {}".format(cmd, rc)
        logging.error(msg + ", stderr: {}, stdout:{}".format(stderr, stdout))
        results['msg'] = msg
        module.fail_json(**results)


@logged
def suma_download():
    """
    Download / Install (or preview) action

    suma_params['action'] should be set to either 'preview' or 'download'.

    First compute all Suma request options. Then preform a Suma preview, parse
    output to check there is something to download, if so, do a suma download
    if needed (if action is Download). If suma download output mentions there
    is downloaded items, then use install_all_updates command to install them.

    note:
        Exits with fail_json in case of error
    """
    global logdir
    global results
    global suma_params

    # Check oslevel format
    if not suma_params['oslevel'].strip() or suma_params['oslevel'].upper() == 'LATEST':
        suma_params['oslevel'] = 'Latest'
    else:
        if re.match(r"^[0-9]{4}(|-00|-00-00|-00-00-0000)$", suma_params['oslevel']):
            msg = "Bad parameter: oslevel is '{}', specify a non 0 value for the Technical Level or the Service Pack"\
                  .format(suma_params['oslevel'])
            logging.error(msg)
            results['msg'] = msg
            module.fail_json(**results)
        elif not re.match(r"^[0-9]{4}-[0-9]{2}(|-[0-9]{2}|-[0-9]{2}-[0-9]{4})$", suma_params['oslevel']):
            msg = "Bad parameter: oslevel is '{}', should repect the format: xxxx-xx or xxxx-xx-xx or xxxx-xx-xx-xxxx"\
                  .format(suma_params['oslevel'])
            logging.error(msg)
            results['msg'] = msg
            module.fail_json(**results)

    # =========================================================================
    # compute SUMA request type based on oslevel property
    # =========================================================================
    rq_type = compute_rq_type(suma_params['oslevel'], suma_params['last_sp'])
    if rq_type == 'ERROR':
        msg = "Bad parameter: oslevel is '{}', parsing error".format(suma_params['action'], suma_params['oslevel'])
        logging.error(msg)
        results['msg'] = msg
        module.fail_json(**results)

    suma_params['RqType'] = rq_type
    logging.debug("SUMA req Type: {}".format(rq_type))

    # =========================================================================
    # compute SUMA request name based on metadata info
    # =========================================================================
    suma_params['RqName'] = compute_rq_name(rq_type, suma_params['oslevel'], suma_params['last_sp'])
    logging.debug("Suma req Name: {}".format(suma_params['RqName']))

    # =========================================================================
    # compute suma dl target
    # =========================================================================
    if not suma_params['download_dir']:
        msg = "Bad parameter: action is {} but download_dir is '{}'".format(suma_params['action'], suma_params['download_dir'])
        logging.error(msg)
        results['msg'] = msg
        module.fail_json(**results)
    else:
        suma_params['DLTarget'] = suma_params['download_dir'].rstrip('/')

    logging.info("The download location will be: {}.".format(suma_params['DLTarget']))
    if not os.path.exists(suma_params['DLTarget']):
        os.makedirs(suma_params['DLTarget'])

    # ========================================================================
    # SUMA command for preview
    # ========================================================================
    rc, stdout = suma_command('Preview')
    logging.debug("SUMA preview stdout:{}".format(stdout))

    # parse output to see if there is something to download
    downloaded = 0
    failed = 0
    skipped = 0
    for line in stdout.rstrip().splitlines():
        line = line.rstrip()
        matched = re.match(r"^\s+(\d+)\s+downloaded$", line)
        if matched:
            downloaded = int(matched.group(1))
            continue
        matched = re.match(r"^\s+(\d+)\s+failed$", line)
        if matched:
            failed = int(matched.group(1))
            continue
        matched = re.match(r"^\s+(\d+)\s+skipped$", line)
        if matched:
            skipped = int(matched.group(1))

    msg = "Preview summary : {} to download, {} failed, {} skipped"\
          .format(downloaded, failed, skipped)
    logging.info(msg)

    # If action is preview or nothing is available to download, we are done
    if suma_params['action'] == 'preview':
        results['meta']['messages'].append(msg)
    if downloaded == 0 and skipped == 0:
        return
    # else continue
    results['meta']['messages'].extend(stdout.rstrip().splitlines())
    results['meta']['messages'].append(msg)

    # ================================================================
    # SUMA command for download
    # ================================================================
    if downloaded != 0:
        rc, stdout = suma_command('Download')
        logging.debug("SUMA dowload stdout:{}".format(stdout))

        # parse output to see if something has been downloaded
        downloaded = 0
        failed = 0
        skipped = 0
        for line in stdout.rstrip().splitlines():
            line = line.rstrip()
            matched = re.match(r"^\s+(\d+)\s+downloaded$", line)
            if matched:
                downloaded = int(matched.group(1))
                continue
            matched = re.match(r"^\s+(\d+)\s+failed$", line)
            if matched:
                failed = int(matched.group(1))
                continue
            matched = re.match(r"^\s+(\d+)\s+skipped$", line)
            if matched:
                skipped = int(matched.group(1))

        msg = "Download summary : {} downloaded, {} failed, {} skipped"\
              .format(downloaded, failed, skipped)

        if downloaded == 0 and skipped == 0:
            # All expected download have failed
            logging.error(msg)
            results['meta']['messages'].append(msg)
            return

        logging.info(msg)
        results['meta']['messages'].extend(stdout.rstrip().splitlines())
        results['meta']['messages'].append(msg)

        if downloaded != 0:
            results['changed'] = True

    # ===========================================================
    # Install updates
    # ===========================================================
    if not suma_params['download_only']:
        cmd = "/usr/sbin/install_all_updates -Yd {}".format(suma_params['DLTarget'])

        logging.debug("SUMA command:{}".format(cmd))
        results['meta']['messages'].append(msg)

        rc, stdout, stderr = module.run_command(cmd)

        results['stdout'] = stdout
        results['stderr'] = stderr
        results['changed'] = True

        if rc != 0:
            msg = "Suma install command '{}' failed with return code {}.".format(cmd, rc)
            logging.error(msg + ", stderr:{}, stdout:{}".format(stderr, stdout))
            msg += " Review {}/suma_debug.log for status.".format(logdir)
            results['msg'] = msg
            module.fail_json(**results)

        logging.info("Suma install command output: {}".format(stdout))


##############################################################################

def main():
    global module
    global results
    global suma_params
    global logdir

    module = AnsibleModule(
        argument_spec=dict(
            action=dict(required=False,
                        choices=['download', 'preview', 'list', 'edit',
                                 'unschedule', 'delete', 'config', 'default'],
                        type='str', default='download'),
            oslevel=dict(required=False, type='str', default='Latest'),
            last_sp=dict(required=False, type='bool', default=False),
            extend_fs=dict(required=False, type='bool', default=True),
            download_dir=dict(required=False, type='path', default='/usr/sys/inst.images'),
            download_only=dict(required=False, type='bool', default=False),
            task_id=dict(required=False, type='str'),
            sched_time=dict(required=False, type='str'),
            description=dict(required=False, type='str'),
            metadata_dir=dict(required=False, type='path', default='/var/adm/ansible/metadata'),
        ),
        required_if=[
            ['action', 'edit', ['task_id']],
            ['action', 'delete', ['task_id']],
            ['action', 'download', ['oslevel']],
            ['action', 'preview', ['oslevel']],
            ['action', 'unschedule', ['task_id']],
        ],
        supports_check_mode=True
    )

    results = dict(
        changed=False,
        msg='',
        stdout='',
        stderr='',
        meta={'messages': []},
    )

    # Open log file
    if not os.path.exists(logdir):
        os.makedirs(logdir, mode=0o744)
    logging.basicConfig(
        filename=logdir + "/suma_debug.log",
        format='[%(asctime)s] %(levelname)s: [%(funcName)s:%(thread)d] %(message)s',
        level=logging.DEBUG)

    logging.debug('*** START ***')
    module.run_command_environ_update = dict(LANG='C', LC_ALL='C', LC_MESSAGES='C', LC_CTYPE='C')

    # ========================================================================
    # Get Module params
    # ========================================================================
    action = module.params['action']

    if module.params['description']:
        suma_params['description'] = module.params['description']
    else:
        suma_params['description'] = "{} request for oslevel {}".format(action, module.params['oslevel'])

    suma_params['action'] = action

    # ========================================================================
    # switch action
    # ========================================================================
    if action == 'list':
        suma_params['task_id'] = module.params['task_id']
        suma_list()

    elif action == 'edit':
        suma_params['task_id'] = module.params['task_id']
        suma_params['sched_time'] = module.params['sched_time']
        suma_edit()

    elif action == 'unschedule':
        suma_params['task_id'] = module.params['task_id']
        suma_unschedule()

    elif action == 'delete':
        suma_params['task_id'] = module.params['task_id']
        suma_delete()

    elif action == 'config':
        suma_config()

    elif action == 'default':
        suma_default()

    elif action == 'download' or action == 'preview':
        suma_params['oslevel'] = module.params['oslevel']
        suma_params['download_dir'] = module.params['download_dir']
        suma_params['metadata_dir'] = module.params['metadata_dir']
        suma_params['download_only'] = module.params['download_only']
        suma_params['last_sp'] = module.params['last_sp']
        suma_params['extend_fs'] = module.params['extend_fs']
        suma_download()

    # ========================================================================
    # Exit
    # ========================================================================

    msg = 'Suma {} completed successfully'.format(action)
    logging.info(msg)
    results['msg'] = msg
    module.exit_json(**results)


if __name__ == '__main__':
    main()
