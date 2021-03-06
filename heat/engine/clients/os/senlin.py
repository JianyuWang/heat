#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from heat.common import exception
from heat.common.i18n import _
from heat.engine.clients import client_plugin
from heat.engine import constraints

from openstack import profile
from openstack import session
from senlinclient import client
from senlinclient.common import exc

CLIENT_NAME = 'senlin'


class SenlinClientPlugin(client_plugin.ClientPlugin):

    service_types = [CLUSTERING] = ['clustering']
    VERSION = '1'

    def _create(self):
        interface = self._get_client_option(CLIENT_NAME, 'endpoint_type')
        prof = profile.Profile()
        prof.set_interface(self.CLUSTERING, interface)
        prof.set_region(self.CLUSTERING, self._get_region_name())
        keystone_session = self.context.keystone_session
        s = session.Session(session=keystone_session,
                            auth=keystone_session.auth,
                            profile=prof)
        return client.Client(self.VERSION, session=s)

    def generate_spec(self, spec_type, spec_props):
        spec = {'properties': spec_props}
        spec['type'], spec['version'] = spec_type.split('-')
        return spec

    def check_action_status(self, action_id):
        action = self.client().get_action(action_id)
        if action.status == 'SUCCEEDED':
            return True
        elif action.status == 'FAILED':
            raise exception.ResourceInError(
                status_reason=action.status_reason,
                resource_status=action.status,
            )
        return False

    def get_profile_id(self, profile_name):
        profile = self.client().get_profile(profile_name)
        return profile.id

    def get_cluster_id(self, cluster_name):
        cluster = self.client().get_cluster(cluster_name)
        return cluster.id

    def get_policy_id(self, policy_name):
        policy = self.client().get_policy(policy_name)
        return policy.id

    def is_not_found(self, ex):
        return isinstance(ex, exc.sdkexc.ResourceNotFound)

    def is_bad_request(self, ex):
        return (isinstance(ex, exc.sdkexc.HttpException) and
                ex.http_status == 400)

    def execute_actions(self, actions):
        all_executed = True
        for action in actions:
            if action['done']:
                continue
            all_executed = False
            if action['action_id'] is None:
                func = getattr(self.client(), action['func'])
                ret = func(**action['params'])
                if isinstance(ret, dict):
                    action['action_id'] = ret['action']
                else:
                    action['action_id'] = ret.location.split('/')[-1]
            else:
                ret = self.check_action_status(action['action_id'])
                action['done'] = ret
            # Execute these actions one by one.
            break
        return all_executed


class ProfileConstraint(constraints.BaseCustomConstraint):
    # If name is not unique, will raise exc.sdkexc.HttpException
    expected_exceptions = (exc.sdkexc.HttpException,)

    def validate_with_client(self, client, profile):
        client.client(CLIENT_NAME).get_profile(profile)


class ClusterConstraint(constraints.BaseCustomConstraint):
    #  If name is not unique, will raise exc.sdkexc.HttpException
    expected_exceptions = (exc.sdkexc.HttpException,)

    def validate_with_client(self, client, value):
        client.client(CLIENT_NAME).get_cluster(value)


class PolicyConstraint(constraints.BaseCustomConstraint):
    #  If name is not unique, will raise exc.sdkexc.HttpException
    expected_exceptions = (exc.sdkexc.HttpException,)

    def validate_with_client(self, client, value):
        client.client(CLIENT_NAME).get_policy(value)


class ProfileTypeConstraint(constraints.BaseCustomConstraint):

    expected_exceptions = (exception.StackValidationFailed,)

    def validate_with_client(self, client, value):
        senlin_client = client.client(CLIENT_NAME)
        type_list = senlin_client.profile_types()
        names = [pt.name for pt in type_list]
        if value not in names:
            not_found_message = (
                _("Unable to find senlin profile type '%(pt)s', "
                  "available profile types are %(pts)s.") %
                {'pt': value, 'pts': names}
            )
            raise exception.StackValidationFailed(message=not_found_message)


class PolicyTypeConstraint(constraints.BaseCustomConstraint):

    expected_exceptions = (exception.StackValidationFailed,)

    def validate_with_client(self, client, value):
        senlin_client = client.client(CLIENT_NAME)
        type_list = senlin_client.policy_types()
        names = [pt.name for pt in type_list]
        if value not in names:
            not_found_message = (
                _("Unable to find senlin policy type '%(pt)s', "
                  "available policy types are %(pts)s.") %
                {'pt': value, 'pts': names}
            )
            raise exception.StackValidationFailed(message=not_found_message)
