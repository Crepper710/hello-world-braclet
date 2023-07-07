# Code from: https://raspberrypi.stackexchange.com/questions/135319/how-can-i-open-a-connection-to-my-raspberry-pi-over-bluetooth-without-having-to

import os

from gi.repository import Gio, GLib
from typing import Callable

def _get_topics():
    from main import topics
    return topics

# Introspection data for DBus
profile_xml = """
<node>
    <interface name="org.bluez.Profile1">
        <method name="Release"/>
        <method name="NewConnection">
            <arg type="o" name="device" direction="in"/>
            <arg type="h" name="fd" direction="in"/>
            <arg type="a{sv}" name="fd_properties" direction="in"/>
        </method>
        <method name="RequestDisconnection">
            <arg type="o" name="device" direction="in"/>
        </method>
    </interface>
</node>
"""


class DbusService:
    """Class used to publish a DBus service on to the DBus System Bus"""
    def __init__(self, introspection_xml, publish_path):
        self.node_info = Gio.DBusNodeInfo.new_for_xml(introspection_xml).interfaces[0]
        # start experiment
        method_outargs = {}
        method_inargs = {}
        property_sig = {}
        for method in self.node_info.methods:
            method_outargs[method.name] = '(' + ''.join([arg.signature for arg in method.out_args]) + ')'
            method_inargs[method.name] = tuple(arg.signature for arg in method.in_args)
        self.method_inargs = method_inargs
        self.method_outargs = method_outargs

        self.con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.con.register_object(
            publish_path,
            self.node_info,
            self.handle_method_call,
            self.prop_getter,
            self.prop_setter)

    def handle_method_call(self,
                           connection: Gio.DBusConnection,
                           sender: str,
                           object_path: str,
                           interface_name: str,
                           method_name: str,
                           params: GLib.Variant,
                           invocation: Gio.DBusMethodInvocation
                           ):
        """
        This is the top-level function that handles method calls to
        the server.
        """
        args = list(params.unpack())
        # Handle the case where it is a Unix filedescriptor
        for i, sig in enumerate(self.method_inargs[method_name]):
            if sig == 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])
        func = self.__getattribute__(method_name)
        result = func(*args)
        if result is None:
            result = ()
        else:
            result = (result,)
        outargs = ''.join([_.signature
                           for _ in invocation.get_method_info().out_args])
        send_result = GLib.Variant(f'({outargs})', result)
        invocation.return_value(send_result)

    def prop_getter(self,
                    connection: Gio.DBusConnection,
                    sender: str,
                    object: str,
                    iface: str,
                    name: str):
        """Return requested values on DBus from Python object"""
        py_value = self.__getattribute__(name)
        signature = self.node_info.lookup_property(name).signature
        if py_value:
            return GLib.Variant(signature, py_value)
        return None

    def prop_setter(self,
                    connection: Gio.DBusConnection,
                    sender: str,
                    object: str,
                    iface: str,
                    name: str,
                    value: GLib.Variant):
        """Set values on Python object from DBus"""
        self.__setattr__(name, value.unpack())
        return True


class Profile(DbusService):

    def __init__(self, introspection_xml, publish_path, io_callback):
        super().__init__(introspection_xml, publish_path)
        self._io_callback = io_callback
        self.fd = -1

    def Release(self):
        print('Release')

    def NewConnection(self, path, fd, properties):
        self.fd = fd
        print(f'NewConnection({path}, {self.fd}, {properties})')
        for key in properties.keys():
            if key == 'Version' or key == 'Features':
                print('  %s = 0x%04x' % (key, properties[key]))
            else:
                print('  %s = %s' % (key, properties[key]))
        io_id = GLib.io_add_watch(self.fd,
                                  GLib.PRIORITY_DEFAULT,
                                  GLib.IO_IN | GLib.IO_PRI,
                                  IOCallbackWrapper(self._io_callback))

    # def io_cb(self, fd, conditions):
    #     data = os.read(fd, 1024)
    #     print('Callback Data: {0}'.format(data.decode('ascii')))
    #     os.write(fd, bytes(list(reversed(data.rstrip()))) + b'\n')
    #     return True

    def RequestDisconnection(self, path):
        print('RequestDisconnection(%s)' % (path))
        if self.fd > 0:
            os.close(self.fd)
            self.fd = -1


def create_main_loop(io_callback):
    obj_mngr = Gio.DBusObjectManagerClient.new_for_bus_sync(
        bus_type=Gio.BusType.SYSTEM,
        flags=Gio.DBusObjectManagerClientFlags.NONE,
        name='org.bluez',
        object_path='/',
        get_proxy_type_func=None,
        get_proxy_type_user_data=None,
        cancellable=None,
    )

    manager = obj_mngr.get_object('/org/bluez').get_interface('org.bluez.ProfileManager1')
    adapter = obj_mngr.get_object('/org/bluez/hci0').get_interface('org.freedesktop.DBus.Properties')
    mainloop = GLib.MainLoop()

    discoverable = adapter.Get('(ss)', 'org.bluez.Adapter1', 'Discoverable')

    if not discoverable:
        print('Making discoverable...')
        adapter.Set('(ssv)', 'org.bluez.Adapter1',
                    'Discoverable', GLib.Variant.new_boolean(True))

    profile_path = '/org/bluez/test/profile'
    server_uuid = '00001101-0000-1000-8000-00805f9b34fb'
    opts = {
        'Version': GLib.Variant.new_uint16(0x0102),
        'AutoConnect': GLib.Variant.new_boolean(True),
        'Role': GLib.Variant.new_string('server'),
        'Name': GLib.Variant.new_string('SerialPort'),
        'Service': GLib.Variant.new_string('00001101-0000-1000-8000-00805f9b34fb'),
        'RequireAuthentication': GLib.Variant.new_boolean(False),
        'RequireAuthorization': GLib.Variant.new_boolean(False),
        'Channel': GLib.Variant.new_uint16(1),
    }

    print('Starting Serial Port Profile...')

    profile = Profile(profile_xml, profile_path, io_callback)

    manager.RegisterProfile('(osa{sv})', profile_path, server_uuid, opts)

    return mainloop

class IOCallbackWrapper:
    def __init__(self, io_cb) -> None:
        self._io_cb = io_cb

    def __call__(self, fd, conditions):
        return self._io_cb(self, fd, conditions)