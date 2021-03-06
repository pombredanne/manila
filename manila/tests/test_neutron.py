# Copyright 2013 OpenStack Foundation
# All Rights Reserved
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
#
# vim: tabstop=4 shiftwidth=4 softtabstop=4

from mock import Mock
from mock import patch
from neutronclient.common import exceptions as neutron_client_exc
from neutronclient.v2_0 import client as clientv20
from oslo.config import cfg
import unittest

from manila import context
from manila.db import base
from manila import exception
from manila.network import neutron
from manila.network.neutron import api as neutron_api
from manila.tests.db import fakes

CONF = cfg.CONF


class FakeNeutronClient(object):

    def create_port(self, body):
        return body

    def delete_port(self, port_id):
        pass

    def show_port(self, port_id):
        pass

    def list_ports(self, **search_opts):
        pass

    def list_networks(self):
        pass

    def show_network(self, network_uuid):
        pass

    def list_extensions(self):
        pass


class NeutronApiTest(unittest.TestCase):

    def setUp(self):
        super(NeutronApiTest, self).setUp()
        self._create_neutron_api()

    @patch.object(base, 'Base', fakes.FakeModel)
    @patch.object(context, 'get_admin_context',
                       Mock(return_value='context'))
    @patch.object(neutron, 'get_client',
                       Mock(return_value=FakeNeutronClient()))
    def _create_neutron_api(self):
        self.neutron_api = neutron_api.API()

    @patch.object(base, 'Base', fakes.FakeModel)
    @patch.object(context, 'get_admin_context',
                       Mock(return_value='context'))
    @patch.object(neutron, 'get_client', Mock())
    def test_create_api_object(self):
        with patch.object(base.Base, '__init__', Mock()):
            neutron_api_obj = neutron_api.API()
            base.Base.__init__.assert_called_once()
            neutron.get_client.assert_called_once_with('context')

    def test_create_port_with_all_args(self):
        port_args = {'tenant_id': 'test tenant', 'network_id': 'test net',
                     'host_id': 'test host', 'subnet_id': 'test subnet',
                     'fixed_ip': 'test ip', 'device_owner': 'test owner',
                     'device_id': 'test device', 'mac_address': 'test mac',
                     'security_group_ids': 'test group',
                     'dhcp_opts': 'test dhcp'}

        with patch.object(self.neutron_api, '_has_port_binding_extension',
                          Mock(return_value=True)):
            port = self.neutron_api.create_port(**port_args)
            self.assertEqual(port['port']['tenant_id'], port_args['tenant_id'])
            self.assertEqual(port['port']['network_id'],
                             port_args['network_id'])
            self.assertEqual(port['port']['binding:host_id'],
                             port_args['host_id'])
            self.assertEqual(port['port']['fixed_ips'][0]['subnet_id'],
                             port_args['subnet_id'])
            self.assertEqual(port['port']['fixed_ips'][0]['ip_address'],
                             port_args['fixed_ip'])
            self.assertEqual(port['port']['device_owner'],
                             port_args['device_owner'])
            self.assertEqual(port['port']['device_id'], port_args['device_id'])
            self.assertEqual(port['port']['mac_address'],
                             port_args['mac_address'])
            self.assertEqual(port['port']['security_groups'],
                             port_args['security_group_ids'])
            self.assertEqual(port['port']['extra_dhcp_opts'],
                             port_args['dhcp_opts'])

    def test_create_port_with_required_args(self):
        port_args = {'tenant_id': 'test tenant', 'network_id': 'test net'}

        with patch.object(self.neutron_api, '_has_port_binding_extension',
                          Mock(return_value=True)):

            port = self.neutron_api.create_port(**port_args)
            self.assertEqual(port['port']['tenant_id'], port_args['tenant_id'])
            self.assertEqual(port['port']['network_id'],
                             port_args['network_id'])

    @patch.object(neutron_api.LOG, 'exception', Mock())
    def test_create_port_exception(self):
        port_args = {'tenant_id': 'test tenant', 'network_id': 'test net'}
        client_create_port_mock = Mock(side_effect=
                                    neutron_client_exc.NeutronClientException)

        with patch.object(self.neutron_api, '_has_port_binding_extension',
                          Mock(return_value=True)):
            with patch.object(self.neutron_api.client, 'create_port',
                              client_create_port_mock):

                self.assertRaises(exception.NetworkException,
                                 self.neutron_api.create_port,
                                 **port_args)
                client_create_port_mock.assert_called_once()
                neutron_api.LOG.exception.assert_called_once()

    @patch.object(neutron_api.LOG, 'exception', Mock())
    def test_create_port_exception_status_409(self):
        port_args = {'tenant_id': 'test tenant', 'network_id': 'test net'}
        client_create_port_mock = Mock(side_effect=
                    neutron_client_exc.NeutronClientException(status_code=409))

        with patch.object(self.neutron_api, '_has_port_binding_extension',
                          Mock(return_value=True)):
            with patch.object(self.neutron_api.client, 'create_port',
                              client_create_port_mock):

                self.assertRaises(exception.PortLimitExceeded,
                                  self.neutron_api.create_port,
                                  **port_args)
                client_create_port_mock.assert_called_once()
                neutron_api.LOG.exception.assert_called_once()

    def test_delete_port(self):
        port_id = 'test port id'
        with patch.object(self.neutron_api.client, 'delete_port',
                          Mock()) as client_delete_port_mock:

            self.neutron_api.delete_port(port_id)
            client_delete_port_mock.assert_called_once_with(port_id)

    def test_list_ports(self):
        search_opts = {'test_option': 'test_value'}
        fake_ports = [{'fake port': 'fake port info'}]
        client_list_ports_mock = Mock(return_value={'ports': fake_ports})

        with patch.object(self.neutron_api.client, 'list_ports',
                          client_list_ports_mock):

            ports = self.neutron_api.list_ports(**search_opts)
            client_list_ports_mock.assert_called_once_with(**search_opts)
            self.assertEqual(ports, fake_ports)

    def test_show_port(self):
        port_id = 'test port id'
        fake_port = {'fake port': 'fake port info'}
        client_show_port_mock = Mock(return_value={'port': fake_port})

        with patch.object(self.neutron_api.client, 'show_port',
                          client_show_port_mock):

            port = self.neutron_api.show_port(port_id)
            client_show_port_mock.assert_called_once_with(port_id)
            self.assertEqual(port, fake_port)

    def test_get_network(self):
        network_id = 'test network id'
        fake_network = {'fake network': 'fake network info'}
        client_show_network_mock = Mock(return_value={'network': fake_network})

        with patch.object(self.neutron_api.client, 'show_network',
                          client_show_network_mock):

            network = self.neutron_api.get_network(network_id)
            client_show_network_mock.assert_called_once_with(network_id)
            self.assertEqual(network, fake_network)

    def test_get_all_network(self):
        fake_networks = [{'fake network': 'fake network info'}]
        client_list_networks_mock = Mock(
                                     return_value={'networks': fake_networks})

        with patch.object(self.neutron_api.client, 'list_networks',
                          client_list_networks_mock):

            networks = self.neutron_api.get_all_networks()
            client_list_networks_mock.assert_called_once()
            self.assertEqual(networks, fake_networks)

    def test_has_port_binding_extension_01(self):
        fake_extensions = [{'name': neutron_api.PORTBINDING_EXT}]
        client_list_ext_mock = Mock(
                                return_value={'extensions': fake_extensions})

        with patch.object(self.neutron_api.client, 'list_extensions',
                          client_list_ext_mock):
            result = self.neutron_api._has_port_binding_extension()
            client_list_ext_mock.assert_called_once()
            self.assertTrue(result)

    def test_has_port_binding_extension_02(self):
        client_list_ext_mock = Mock()
        self.neutron_api.extensions =\
                        {neutron_api.PORTBINDING_EXT: 'extension description'}

        with patch.object(self.neutron_api.client, 'list_extensions',
                          client_list_ext_mock):
            result = self.neutron_api._has_port_binding_extension()
            client_list_ext_mock.assert_not_called_once()
            self.assertTrue(result)

    def test_has_port_binding_extension_03(self):
        client_list_ext_mock = Mock()
        self.neutron_api.extensions =\
                        {'neutron extension X': 'extension description'}

        with patch.object(self.neutron_api.client, 'list_extensions',
                          client_list_ext_mock):
            result = self.neutron_api._has_port_binding_extension()
            client_list_ext_mock.assert_not_called_once()
            self.assertFalse(result)


class TestNeutronClient(unittest.TestCase):

    @patch.object(clientv20.Client, '__init__', Mock(return_value=None))
    def test_get_client_with_token(self):
        client_args = {'endpoint_url': CONF.neutron_url,
                       'timeout': CONF.neutron_url_timeout,
                       'insecure': CONF.neutron_api_insecure,
                       'ca_cert': CONF.neutron_ca_certificates_file,
                       'token': 'test_token',
                       'auth_strategy': None}
        my_context = context.RequestContext('test_user', 'test_tenant',
                                            auth_token='test_token',
                                            is_admin=False)

        neutron.get_client(my_context)
        clientv20.Client.__init__.assert_called_once_with(**client_args)

    @patch.object(clientv20.Client, '__init__', Mock(return_value=None))
    def test_get_client_no_token(self):
        my_context = context.RequestContext('test_user', 'test_tenant',
                                            is_admin=False)

        self.assertRaises(neutron_client_exc.Unauthorized,
                          neutron.get_client,
                          my_context)

    @patch.object(clientv20.Client, '__init__', Mock(return_value=None))
    def test_get_client_admin_context(self):
        client_args = {'endpoint_url': CONF.neutron_url,
                       'timeout': CONF.neutron_url_timeout,
                       'insecure': CONF.neutron_api_insecure,
                       'ca_cert': CONF.neutron_ca_certificates_file,
                       'username': CONF.neutron_admin_username,
                       'tenant_name': CONF.neutron_admin_tenant_name,
                       'password': CONF.neutron_admin_password,
                       'auth_url': CONF.neutron_admin_auth_url,
                       'auth_strategy': CONF.neutron_auth_strategy}
        my_context = context.RequestContext('test_user', 'test_tenant',
                                            is_admin=True)

        neutron.get_client(my_context)
        clientv20.Client.__init__.assert_called_once_with(**client_args)
