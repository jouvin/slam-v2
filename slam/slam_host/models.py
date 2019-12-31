"""
As we use django models.Model, pylint fail to find objects method. We must disable pylint
test E1101 (no-member)
"""
# pylint: disable=E1101
from django.db import models
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db.utils import IntegrityError

from slam_core.utils import error_message
from slam_hardware.models import Interface, Hardware
from slam_network.models import Network, Address
from slam_domain.models import DomainEntry, Domain


class Host(models.Model):
    """
    Host represent a association between hardware, network and domain name service
    """
    name = models.CharField(max_length=150, unique=True)
    addresses = models.ManyToManyField(Address)
    interface = models.ForeignKey(Interface, on_delete=models.DO_NOTHING, null=True, blank=True)
    network = models.ForeignKey(Network, on_delete=models.DO_NOTHING, null=True, blank=True)

    @staticmethod
    def create(name, address=None, interface=None, network=None, dns_entry=None):
        """
        This is a custom way to create a host
        :param name: name of the host
        :param address: IP address for the host
        :param interface: interface to bind
        :param network: network to bind (if ip is fixed, ip must be in this network)
        :param dns_entry: DNS name of the host
        :return:
        """
        interface_host = None
        network_host = None
        address_host = None
        if interface is not None:
            try:
                interface_host = Interface.objects.get(mac_address=interface)
            except ObjectDoesNotExist:
                # If the interface not exist, we create a new one
                result = Interface.create(mac_address=interface, hardware=name)
                if result['status'] != 'done':
                    return result
                interface_host = Interface.objects.get(mac_address=interface)
        if network is not None:
            try:
                network_host = Network.objects.get(name=network)
            except ObjectDoesNotExist as err:
                return {
                    'host': name,
                    'status': 'failed',
                    'message': '{}'.format(err)
                }
        # if dns_entry is not None:
        #     try:
        #         domain_entry = Domain.objects.get(name=dns_entry['domain'])
        #     except ObjectDoesNotExist as err:
        #         return {
        #             'host': name,
        #             'status': 'failed',
        #             'message': '{}'.format(err)
        #         }
        #     if 'ns_type' in dns_entry:
        #         try:
        #             dns_entry_host = DomainEntry.objects.get(name=dns_entry['name'],
        #                                                      domain=domain_entry,
        #                                                      type=dns_entry['ns_type'])
        #         except ObjectDoesNotExist:
        #             # If dns_entry not exist, we create a new one
        #             result = DomainEntry.create(name=dns_entry['name'], domain=dns_entry['domain'],
        #                                         type=dns_entry['ns_type'])
        #             if result['status'] != 'done':
        #                 return result
        #             dns_entry_host = DomainEntry.objects.get(name=dns_entry['name'],
        #                                                      domain=domain_entry,
        #                                                      type=dns_entry['ns_type'])
        #     else:
        #         try:
        #             dns_entry_host = DomainEntry.objects.get(name=dns_entry['name'],
        #                                                      domain=domain_entry)
        #         except ObjectDoesNotExist:
        #             # If dns_entry not exist, we create a new one
        #             result = DomainEntry.create(name=dns_entry['name'], domain=dns_entry['domain'])
        #             if result['status'] != 'done':
        #                 return result
        #             dns_entry_host = DomainEntry.objects.get(name=dns_entry['name'],
        #                                                      domain=domain_entry)
        if address is not None:
            try:
                address_host = Address.objects.get(ip=address)
            except ObjectDoesNotExist:
                # If address not exist, we create it
                network_host = Address.network(address)
                if dns_entry is not None:
                    result = Address.create(ip=address, network=network_host.name,
                                            ns_entries=[dns_entry])
                    if result['status'] != 'done':
                        return result
                else:
                    result = Address.create(ip=address, network=network_host.name)
                    if result['status'] != 'done':
                        return result
                address_host = Address.objects.get(ip=address)
        options = {
            'name': name,
            'interface': interface_host,
            'network': network_host,
            # 'dns_entry': dns_entry_host
        }
        try:
            host = Host(**options)
            host.full_clean()
            host.save()
            if address_host is not None:
                host.addresses.add(address_host)
            return {
                'host': name,
                'status': 'done'
            }
        except (ObjectDoesNotExist, IntegrityError, ValidationError) as err:
            return error_message('host', name, err)

    @staticmethod
    def update(name, addresses=None, interface=None, network=None, dns_entry=None):
        """
        This is a custom method to update a host
        :param name: name of the host
        :param addresses: IP address of the host
        :param interface: mac-address of the host
        :param network: network of the host
        :param dns_entry: DNS entry of the host
        :return:
        """
        try:
            host = Host.objects.get(name=name)
            if interface is not None:
                host.interface = Interface.objects.get(mac_address=interface)
            if network is not None:
                host.network = Network.objects.get(name=network)
            if dns_entry is not None:
                domain_entry = Domain.objects.get(name=dns_entry['domain'])
                host.dns_entry = DomainEntry.objects.get(name=dns_entry['ns'], domain=domain_entry)
            try:
                host.full_clean()
            except ValidationError as err:
                return error_message('host', name, err)
            host.save()
        except ObjectDoesNotExist as err:
            return error_message('host', name, err)
        return {
            'host': name,
            'status': 'done'
        }

    @staticmethod
    def remove(name, addresses=True, hardware=False):
        """
        This method is a custom way to delete a host.
        :param name: name of host to delete
        :param addresses: if set to True, we also delete all addresses (default: True)
        :param hardware: if set to True, we also delete hardware (default: False)
        :param dns_entry: if set to True, we also delete dns_entry (default: True)
        :return:
        """
        addresses_host = None
        hardware_host = None
        # dns_entry_host = None
        try:
            host = Host.objects.get(name=name)
        except ObjectDoesNotExist as err:
            return error_message('host', name, err)
        if addresses:
            addresses_host = host.addresses.all()
        if hardware:
            hardware_host = host.interface.hardware
        try:
            host.delete()
        except IntegrityError as err:
            return error_message('host', name, err)
        if addresses_host is not None:
            for address in addresses_host:
                try:
                    address.delete()
                except IntegrityError as err:
                    return error_message('host', name, err)
        if hardware_host is not None:
            try:
                host.interface.hardware.delete()
            except IntegrityError as err:
                return error_message('host', name, err)
        return {
            'host': name,
            'status': 'done'
        }

    @staticmethod
    def get(name):
        """
        This is a custom method to get a specific host
        :param name: name of the host
        :return:
        """
        result = {
            'host': name,
        }
        try:
            host = Host.objects.get(name=name)
        except ObjectDoesNotExist as err:
            return error_message('host', name, err)
        result_addresses = []
        for address in host.addresses.all():
            result_addresses.append(address.ip)
        result['network'] = {
            'addresses': result_addresses
        }
        if host.interface is not None:
            result['interface'] = host.interface.mac_address
        if host.network is not None:
            result['network']['name'] = host.network.name
        if host.dns_entry is not None:
            result['dns-entry'] = '{}.{} {}'.format(host.dns_entry.name,
                                                    host.dns_entry.domain.name,
                                                    host.dns_entry.type)
        return result

    @staticmethod
    def search(filters=None):
        """
        This is a custom method to get all hosts that match the filters

        :param filters: a dict of field / regex
        :return:
        """
        if filters is None:
            hosts = Host.objects.all()
        else:  # We suppose filter as been construct outside models class
            hosts = Host.objects.filter(**filters)
        result = []
        for host in hosts:
            result_host = {
                'name': host.name,
                # 'network': host.network.name,
            }
            if host.network is not None:
                result_host['network'] = host.network.name
            result.append(result_host)
        return result
