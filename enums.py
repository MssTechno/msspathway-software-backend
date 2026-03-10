from enum import Enum

class ClientStatus(str, Enum):
    active = "A"
    terminated = "T"
    pass_status = "P"
    completed = "C"