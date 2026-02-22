# waldoctl

Shared interface definitions for robot arm control. Provides abstract base classes (ABCs) that define the contract between robot arm backends and frontend applications.

Named after Robert A. Heinlein's 1942 short story *Waldo*, in which the protagonist invents remote manipulator arms -- the origin of the real-world term "waldo" for teleoperated mechanical hands.

## Installation

```bash
pip install -e .
```

## Usage

Backends inherit from the ABCs and implement required methods:

```python
from waldoctl import Robot, RobotClient

class MyRobot(Robot):
    ...

class MyClient(RobotClient):
    ...
```

Required methods are marked with `@abstractmethod`. Optional features have concrete defaults that backends override as needed.
