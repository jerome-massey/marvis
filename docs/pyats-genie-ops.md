# Genie Operational Recipes

> **Note:**
> This section assumes pyATS and Genie are installed and ready to be used.
> It also assumes you have a testbed file ready to be used with a device.

## 1. Summary

Genie Ops learns everything that can be learned about a feature's operational state and packs it into one structured object. This structure is common for all OSes.

**Use cases:**
- Learn all interfaces on a device and their operational state
- Learn any protocol state (e.g., BGP, OSPF, ACL, Dot1x, LLDP)
- Device state (platforms, linecards, etc.)
- Non-networking purposes (e.g., website info with Selenium)

All supported features can be seen on the [models page](<http>). Each object follows a structure which can also be seen there.

**Examples:**
- Learn a feature and retrieve values from the structure (e.g., check if a particular interface is up)
- Use the Find object to navigate learned data
- Take a snapshot and compare it later to check for changes

## 2. Retrieve a Snapshot of the Operational State

Learning a device feature is easy. Ops objects learn everything about a device feature (e.g., OSPF, interface, etc.) by sending multiple commands and creating a structured object.

```python
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface

testbed = testbed.load(testbed=<path of testbed file>)
uut = testbed.devices['uut']
uut.connect()

interface = Interface(device=uut)
interface.learn()

import pprint
pprint.pprint(interface.info)
```

**Sample output:**
```python
{'Ethernet2/1': {'auto_negotiate': False,
                 'bandwidth': 1000000,
                 'counters': {'in_broadcast_pkts': 0,
                              ...},
                 'delay': 10,
                 'duplex_mode': 'full',
                 'enabled': True,
                 ...}}
```

Use `device.learn('all')` to learn all supported features on the device. The result is a dictionary like `{'interface': <Interface object>}`. If an exception occurs, the feature object will be the exception object.

## 3. Get Partial State of a Feature (Command-Based)

To reduce execution time, you can learn from specific commands only.

```python
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface
from genie.libs.parser.nxos.show_interface import ShowVrfAllInterface

testbed = testbed.load(testbed=<path of testbed file>)
uut = testbed.devices['uut']
uut.connect()

interface = Interface(device=uut, commands=[ShowVrfAllInterface])
interface.learn()

import pprint
pprint.pprint(interface.info)
```

## 4. Get Partial State of a Feature (Attribute-Based)

You can also specify variables you care about. Only related commands will be sent.

```python
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface

testbed = testbed.load(testbed=<path of testbed file>)
uut = testbed.devices['uut']
uut.connect()

interface = Interface(device=uut, attributes=['info[(.*)][duplex_mode]'])
interface.learn()

import pprint
pprint.pprint(interface.info)
```

## 5. Use Ops Object to Verify State

Ops has a built-in verify mode. Learn a feature and verify if it’s as expected, retrying if not.

```python
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface

testbed = testbed.load(testbed=<path of testbed file>)
uut = testbed.devices['uut']
uut.connect()

def verify_interface_status(obj):
    for intf in obj.info:
        if obj.info[intf].get('oper_status') == 'up':
            return
    raise Exception("Could not find any up interface")

interface = Interface(device=uut)
interface.learn_poll(verify=verify_interface_status, sleep=5, attempt=6)
```

## 6. Compare Two Feature Snapshots (Diff Two Ops Objects)

Take snapshots at different times and compare them to see if the network state has changed.

```python
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface

testbed = testbed.load(testbed=<path of testbed file>)
uut = testbed.devices['uut']
uut.connect()

interface = Interface(device=uut)
interface.learn()

# Modify an interface, then take a new snapshot
for intf in interface.info:
    if interface.info[intf].get('oper_status') == 'up':
        up_interface = intf
        break
else:
    raise Exception("Could not find any up interface")

uut.configure(f"""
interface {up_interface}
 shut
""")

interface_after = Interface(device=uut)
interface_after.learn()

import pprint
pprint.pprint(interface.info)
diff = interface_after.diff(interface)
print(diff)

uut.configure(f"""
interface {up_interface}
 no shut
""")
```

## 7. Save Snapshot to File and Reuse Later

You can save the object as a file and compare it later.

```python
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface

testbed = testbed.load(testbed=<path of testbed file>)
uut = testbed.devices['uut']
uut.connect()

interface = Interface(device=uut)
interface.learn()
with open(file, 'wb') as f:
    f.write(interface.pickle(interface))
```

Later, you can load and compare:

```python
from genie.ops.base import Base

with open(file, 'rb') as f:
    interface = Base.unpickle(f.read())
```

## 8. Connection Pool with Ops (Learn Faster!)

Genie provides asynchronous execution with a connection pool, sending commands in parallel for better performance.

```python
from genie import testbed
from genie.libs.ops.interface.nxos.interface import Interface

testbed = testbed.load(testbed=<path of testbed file>)
uut = testbed.devices['uut']

uut.start_pool(alias='a', size=1)
interface = Interface(device=uut)
interface.learn()
```

You can also use multiple connections (e.g., management port):

```yaml
devices:
  nx-osv-1:
    alias: 'uut'
    type: 'Nexus'
    os: 'nxos'
    tacacs:
      login_prompt: "login:"
      password_prompt: "Password:"
      username: "admin"
    passwords:
      tacacs: Cisc0123
      enable: admin
      line: admin
    connections:
      defaults:
        class: 'unicon.Unicon'
      a:
        protocol: telnet
        ip: "172.25.192.90"
        port: 17052
      vty:
        protocol: telnet
        ip: "10.1.1.2"
```

Start a pool with more connections:

```python
uut.start_pool(alias='vty', size=10)
interface = Interface(device=uut)
```

Connection pool increases performance by using multiple connections.

---

**More information:**
- [Ops page](<http>)
- [Connection pool documentation](<http>)
- [Official Python pickle documentation](<http>)
