ROLE_SUPER_ADMIN = 1
ROLE_COORDINATOR = 2
ROLE_OPERATOR = 3
ROLE_OBSERVER = 4

class EquipmentStatus:
    FUNCTIONAL = 'Functional'
    DEPLOYED = 'Deployed'
    ACTIVE = 'Active'
    IN_STORAGE = 'In Storage'
    RETIRED = 'Retired'
    NEEDS_MAINTENANCE = 'Needs Maintenance'

    @classmethod
    def healthy_states(cls):
        return (cls.FUNCTIONAL.lower(), cls.DEPLOYED.lower(), cls.ACTIVE.lower())

class TrapCondition:
    OK = 'Ok'
    GOOD = 'Good'
    FUNCTIONAL = 'Functional'

    @classmethod
    def healthy_states(cls):
        return (cls.OK.lower(), cls.GOOD.lower(), cls.FUNCTIONAL.lower())
