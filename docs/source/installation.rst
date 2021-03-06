.. ...........................................................................
.. © Copyright IBM Corporation 2020                                          .
.. ...........................................................................

Installation
============

You can install the **IBM Power Systems AIX collection** using one of these options:
Ansible Galaxy, Ansible Automation Hub, or a local build.

For more information on installing collections, see `using collections`_.

.. _using collections:
   https://docs.ansible.com/ansible/latest/user_guide/collections_using.html

Ansible Galaxy
--------------
Galaxy enables you to quickly configure your automation project with content
from the Ansible community.

Galaxy provides prepackaged units of work known as collections. You can use the
`ansible-galaxy`_ command with the option ``install`` to install a collection on
your system (control node) hosted in Galaxy.

By default, the `ansible-galaxy`_ command installs the latest available
collection, but you can add a version identifier to install a specific version.
Before installing a collection from Galaxy, review all the available versions.
Periodically, new releases containing enhancements and features you might be
interested in become available.

The ansible-galaxy command ignores any pre-release versions unless
the ``==`` range identifier is set to that pre-release version.
A pre-release version is denoted by appending a hyphen and a series of
dot separated identifiers immediately following the patch version. The
**IBM Power Systems AIX collection** releases collections with the pre-release
naming convention such as **1.0.0-beta1** that would require a range identifier.

Here is an example of installing a pre-release collection:

.. code-block:: sh

   $ ansible-galaxy collection install ibm.power_aix:==1.0.0-beta1


If you have installed a prior version, you must overwrite an existing
collection with the ``--force`` option.

Here are a few examples of installing the **IBM Power Systems AIX collection**:

.. code-block:: sh

   $ ansible-galaxy collection install ibm.power_aix
   $ ansible-galaxy collection install -f ibm.power_aix
   $ ansible-galaxy collection install --force ibm.power_aix

The collection installation progress will be output to the console. Note the
location of the installation so that you can review other content included with
the collection, such as the sample playbook. By default, collections are
installed in ``~/.ansible/collections``; see the sample output.

.. _ansible-galaxy:
   https://docs.ansible.com/ansible/latest/cli/ansible-galaxy.html

.. code-block:: sh

   Process install dependency map
   Starting collection install process
   Installing 'ibm.power_aix:1.0.0' to '/Users/user/.ansible/collections/ansible_collections/ibm/power_aix'

After installation, the collection content will resemble this hierarchy: :

.. code-block:: sh

   ├── collections/
   │  ├── ansible_collections/
   │      ├── ibm/
   │          ├── power_aix/
   │              ├── docs/
   │              ├── playbooks/
   │                  ├── group_vars/
   │                  ├── host_vars/
   │              ├── plugins/
   │                  ├── action/
   │                  ├── module_utils/
   │                  ├── modules/
   │                  └── filter/


You can use the `-p` option with `ansible-galaxy` to specify the installation
path, such as:

.. code-block:: sh

   $ ansible-galaxy collection install ibm.power_aix -p /home/ansible/collections

When using the `-p` option to specify the install path, use one of the values
configured in COLLECTIONS_PATHS, as this is where Ansible itself will expect
to find collections.

For more information on installing collections with Ansible Galaxy,
see `installing collections`_.

.. _installing collections:
   https://docs.ansible.com/ansible/latest/user_guide/collections_using.html#installing-collections-with-ansible-galaxy

Automation Hub and Private Galaxy server
----------------------------------------
Configuring access to a private Galaxy server follows the same instructions
that you would use to configure your client to point to Automation Hub. When
hosting a private Galaxy server or pointing to Hub, available content is not
always consistent with what is available on the community Galaxy server.

You can use the `ansible-galaxy`_ command with the option ``install`` to
install a collection on your system (control node) hosted in Automation Hub
or a private Galaxy server.

By default, the ``ansible-galaxy`` command is configured to access
``https://galaxy.ansible.com`` as the server when you install a
collection. The `ansible-galaxy` client can be configured to point to Hub or
other servers, such as a privately running Galaxy server, by configuring the
server list in the ``ansible.cfg`` file.

Ansible searches for ``ansible.cfg`` in the following locations in this order:

   * ANSIBLE_CONFIG (environment variable if set)
   * ansible.cfg (in the current directory)
   * ~/.ansible.cfg (in the home directory)
   * /etc/ansible/ansible.cfg

To configure a Galaxy server list in the ansible.cfg file:

  * Add the server_list option under the [galaxy] section to one or more
    server names.
  * Create a new section for each server name.
  * Set the url option for each server name.

For Automation Hub, you additionally need to:

  * Set the auth_url option for each server name.
  * Set the API token for each server name. For more information on API tokens,
    see `Get API token from the version dropdown to copy your API token`_.

.. _Get API token from the version dropdown to copy your API token:
   https://cloud.redhat.com/ansible/automation-hub/token/

The following example shows a configuration for Automation Hub, a private
running Galaxy server, and Galaxy:

.. code-block:: yaml

   [galaxy]
   server_list = automation_hub, galaxy, private_galaxy

   [galaxy_server.automation_hub]
   url=https://cloud.redhat.com/api/automation-hub/
   auth_url=https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token
   token=<hub_token>

   [galaxy_server.galaxy]
   url=https://galaxy.ansible.com/

   [galaxy_server.private_galaxy]
   url=https://galaxy-dev.ansible.com/
   token=<private_token>

For more configuration information, see
`configuring the ansible-galaxy client`_ and `Ansible Configuration Settings`_.

.. _configuring the ansible-galaxy client:
   https://docs.ansible.com/ansible/latest/user_guide/collections_using.html#configuring-the-ansible-galaxy-client

.. _Ansible configuration Settings:
   https://docs.ansible.com/ansible/latest/reference_appendices/config.html


Local build
-----------

You can use the ``ansible-galaxy collection install`` command to install a
collection built from source. Version builds are available in the ``builds``
directory of the IBM ansible-power-aix Git repository. The archives can be
installed locally without having to use Hub or Galaxy.

To install a build from the ansible-power-aix Git repository:

   1. Obtain a local copy from the Git repository:

      .. note::
         * Collection archive names will change depending on the release version.
         * They adhere to this convention **<namespace>-<collection>-<version>.tar.gz**, for example, **ibm-power_aix-1.0.0.tar.gz**


   2. Install the local collection archive:

      .. code-block:: sh

         $ ansible-galaxy collection install ibm-power_aix-1.0.0.tar.gz

      In the output of collection installation, note the installation path to access the sample playbook:

      .. code-block:: sh

         Process install dependency map
         Starting collection install process
         Installing 'ibm.power_aix:1.0.0' to '/Users/user/.ansible/collections/ansible_collections/ibm/power_aix'

      You can use the ``-p`` option with ``ansible-galaxy`` to specify the
      installation path, for example, ``ansible-galaxy collection install ibm-power_aix-1.0.0.tar.gz -p /home/ansible/collections``.

      For more information, see `installing collections with Ansible Galaxy`_.

      .. _installing collections with Ansible Galaxy:
         https://docs.ansible.com/ansible/latest/user_guide/collections_using.html#installing-collections-with-ansible-galaxy


