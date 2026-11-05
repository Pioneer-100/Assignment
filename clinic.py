from abc import ABC, abstractmethod
from pathlib import Path

# ----------------------------- Exceptions -----------------------------

class ClinicError(Exception):
    """Base class for expected clinic rule violations."""


class ValidationError(ClinicError):
    pass


class BookingError(ClinicError):
    pass


class AppointmentStateError(ClinicError):
    pass


class DuplicateIDError(ClinicError):
    pass


class LogError(RuntimeError):
    """Raised when the audit log cannot be safely written."""


# ------------------------------- Clock ---------------------------------

class Clock(ABC):
    @abstractmethod
    def now(self):
        raise NotImplementedError


class ManualClock(Clock):
    """A controllable clock for predictable tests and demonstrations."""

    def __init__(self, current_hour=0):
        self.set_hour(current_hour)

    def now(self):
        return self._current_hour

    def set_hour(self, hour):
        if (not isinstance(hour, int) or isinstance(hour, bool)
                or not 0 <= hour <= 168):
            raise ValidationError("Clock hour must be an integer between 0 and 168.")
        self._current_hour = hour


# ------------------------------- Person --------------------------------

class Person(ABC):
    constructor_calls = 0

    def __init__(self, name, person_id, **kwargs):
        if kwargs:
            raise TypeError(f"Unexpected arguments: {', '.join(kwargs)}")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("Name cannot be empty.")
        if (not isinstance(person_id, int) or isinstance(person_id, bool)
                or person_id <= 0):
            raise ValidationError("ID must be a positive integer.")

        self._name = name.strip()
        self._id = person_id
        Person.constructor_calls += 1

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._id

    @abstractmethod
    def role(self):
        raise NotImplementedError


# ------------------------------- Patient -------------------------------

class Patient(Person):
    def __init__(self, name, person_id, patient_type="visitor", is_emergency=False):
        super().__init__(name, person_id)

        allowed_types = {"student", "staff-member", "visitor"}
        if patient_type not in allowed_types:
            raise ValidationError(
                "Patient type must be student, staff-member, or visitor."
            )
        if not isinstance(is_emergency, bool):
            raise ValidationError("is_emergency flag must be a boolean.")

        self._patient_type = patient_type
        self._is_emergency = is_emergency

    @property
    def patient_type(self):
        return self._patient_type

    @property
    def is_emergency(self):
        return self._is_emergency

    def set_emergency(self, flag):
        if not isinstance(flag, bool):
            raise ValidationError("is_emergency flag must be a boolean.")
        self._is_emergency = flag

    def role(self):
        return "Patient"

    def payment_rate(self):
        rates = {
            "student": 0.50,
            "staff-member": 0.00,
            "visitor": 1.00,
        }
        return rates[self._patient_type]


# -------------------------------- Staff ---------------------------------

class Staff(Person, ABC):
    def __init__(self, name, person_id, **kwargs):
        super().__init__(name, person_id, **kwargs)

    @abstractmethod
    def fee(self):
        raise NotImplementedError


class Doctor(Staff):
    def __init__(self, name, person_id, p_value=0, **kwargs):
        if (not isinstance(p_value, int) or isinstance(p_value, bool)
                or p_value < 0):
            raise ValidationError("P_VALUE must be a non-negative integer.")
        self._p_value = p_value
        super().__init__(name, person_id, **kwargs)

    def role(self):
        return "Doctor"

    def fee(self):
        return 40 + 5 * (self._p_value % 5)


class Nurse(Staff):
    def __init__(self, name, person_id, p_value=0, **kwargs):
        if (not isinstance(p_value, int) or isinstance(p_value, bool)
                or p_value < 0):
            raise ValidationError("P_VALUE must be a non-negative integer.")
        self._p_value = p_value
        super().__init__(name, person_id, **kwargs)

    def role(self):
        return "Nurse"

    def fee(self):
        return 10 + (self._p_value % 3)


class Pharmacist(Staff):
    def __init__(self, name, person_id, **kwargs):
        super().__init__(name, person_id, **kwargs)

    def role(self):
        return "Pharmacist"

    def fee(self):
        return 5


# ---------------------- Multiple inheritance: Q5 ----------------------

class Lecturer(Person):
    def __init__(self, name, person_id, module_name, **kwargs):
        if not isinstance(module_name, str) or not module_name.strip():
            raise ValidationError("Module name cannot be empty.")
        self._module_name = module_name.strip()
        # Cooperative super() initializes the shared Person base once.
        super().__init__(name, person_id, **kwargs)

    @property
    def module_name(self):
        return self._module_name

    def role(self):
        return "Lecturer"


class MedicalLecturer(Doctor, Lecturer):
    """
    Diamond inheritance:
                 Person
                /      \\
             Staff    Lecturer
                \\      /
             MedicalLecturer

    Python's method resolution order and cooperative super() initialize
    the shared Person base only once.
    """

    def __init__(self, name, person_id, module_name, p_value=0):
        super().__init__(
            name=name,
            person_id=person_id,
            module_name=module_name,
            p_value=p_value,
        )

    def role(self):
        return "Doctor and Lecturer"


# ----------------------------- Appointment -----------------------------

# INVARIANTS FOR Appointment:
# 1. 0 < _id (Appointment ID is a strictly positive integer).
# 2. _patient is an instance of Patient and _staff is an instance of Staff.
# 3. 0 <= _start_hour < 168 (Appointment start hour is within the 168-hour week).
# 4. _duration_hours == 1 (Every appointment lasts exactly 1 hour).
# 5. _status in {"PENDING", "CONFIRMED", "CANCELLED"}.
# 6. Once _status == "CANCELLED", it is terminal and can never transition back.
# 7. Only "PENDING" appointments can transition to "CONFIRMED".
# 8. If _status == "CANCELLED", _cancellation_reason is a non-empty string.
class Appointment:
    VALID_STATUSES = {"PENDING", "CONFIRMED", "CANCELLED"}

    def __init__(self, appointment_id, patient, staff, start_hour):
        if (not isinstance(appointment_id, int) or isinstance(appointment_id, bool)
                or appointment_id <= 0):
            raise ValidationError("Appointment ID must be a positive integer.")
        if (not isinstance(start_hour, int) or isinstance(start_hour, bool)
                or not 0 <= start_hour < 168):
            raise ValidationError("Appointment start hour must be between 0 and 167.")
        if not isinstance(patient, Patient):
            raise ValidationError("Invalid patient.")
        if not isinstance(staff, Staff):
            raise ValidationError("Invalid staff member.")

        self._id = appointment_id
        self._patient = patient
        self._staff = staff
        self._start_hour = start_hour
        self._duration_hours = 1
        self._status = "PENDING"
        self._cancellation_reason = None

    @property
    def id(self):
        return self._id

    @property
    def patient(self):
        return self._patient

    @property
    def staff(self):
        return self._staff

    @property
    def start_hour(self):
        return self._start_hour

    @property
    def duration_hours(self):
        return self._duration_hours

    @property
    def status(self):
        return self._status

    @property
    def cancellation_reason(self):
        return self._cancellation_reason

    def price(self):
        return self._staff.fee() * self._patient.payment_rate()

    def confirm(self):
        if self._status != "PENDING":
            raise AppointmentStateError("Only pending appointments can be confirmed.")
        self._status = "CONFIRMED"

    def cancel(self, current_hour, reason="cancelled"):
        if self._status == "CANCELLED":
            raise AppointmentStateError("Appointment already cancelled.")
        if current_hour >= self._start_hour:
            raise AppointmentStateError(
                "Cannot cancel an appointment that has already started."
            )
        if (self._status == "CONFIRMED"
                and self._start_hour - current_hour < 2):
            raise AppointmentStateError(
                "A confirmed appointment must be cancelled at least 2 hours before start."
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("Cancellation reason cannot be empty.")

        self._status = "CANCELLED"
        self._cancellation_reason = reason.strip()


# ------------------------------ Audit log ------------------------------

class ActionLog:
    """Context manager that records an outcome and always closes the log file."""

    def __init__(self, path, action):
        self.path = Path(path)
        self.action = action
        self.file = None

    def __enter__(self):
        try:
            self.file = self.path.open("a", encoding="utf-8")
            print("[log] opened")
            return self
        except OSError as exc:
            raise LogError(f"Could not open appointment log: {exc}") from exc

    def __exit__(self, exc_type, exc_value, traceback):
        write_error = None
        try:
            outcome = "SUCCESS" if exc_type is None else "FAILED"
            detail = "completed" if exc_value is None else str(exc_value)
            self.file.write(f"{outcome} {self.action}: {detail}\n")
            self.file.flush()
        except OSError as exc:
            write_error = exc
        finally:
            try:
                if self.file is not None:
                    self.file.close()
            except OSError as exc:
                if write_error is None:
                    write_error = exc
            print("[log] closed")

        if write_error is not None:
            raise LogError(
                f"Could not safely write/close appointment log: {write_error}"
            )
        return False


# ----------------------------- Clinic --------------------------------

# INVARIANTS FOR Clinic:
# 1. All IDs in self.__person_ids and self.__appointment_ids are globally unique and disjoint.
# 2. For every patient_id in self.__patients, self.__patients[patient_id].id == patient_id.
# 3. For every staff_id in self.__staff, self.__staff[staff_id].id == staff_id.
# 4. For every appt_id in self.__appointments, self.__appointments[appt_id].id == appt_id.
# 5. At any given hour h, no patient and no staff member has more than one active (non-cancelled) appointment.
# 6. Internal dictionaries (__patients, __staff, __appointments, __person_ids, __appointment_ids) are never returned directly; all query methods return immutable snapshots (tuples).
class Clinic:
    """
    Manages patients, staff, and appointments with audit logging and emergency booking support.
    """

    def __init__(self, clock, log_path="appointment_log.txt"):
        if not isinstance(clock, Clock):
            raise ValidationError("Clinic requires a Clock object.")

        self._clock = clock
        self._log_path = log_path
        self.__patients = {}
        self.__staff = {}
        self.__person_ids = set()
        self.__appointments = {}
        self.__appointment_ids = set()

    def _action(self, action):
        return ActionLog(self._log_path, action)

    def register_patient(self, patient):
        with self._action(f"register patient #{getattr(patient, 'id', '?')}"):
            if not isinstance(patient, Patient):
                raise ValidationError("Only Patient objects can be registered as patients.")

            if patient.id in self.__person_ids or patient.id in self.__appointment_ids:
                raise DuplicateIDError(f"ID {patient.id} is already in use.")

            self.__patients[patient.id] = patient
            self.__person_ids.add(patient.id)
            return patient

    def register_staff(self, staff):
        with self._action(f"register staff #{getattr(staff, 'id', '?')}"):
            if not isinstance(staff, Staff):
                raise ValidationError("Only Staff objects can be registered as staff.")

            if staff.id in self.__person_ids or staff.id in self.__appointment_ids:
                raise DuplicateIDError(f"ID {staff.id} is already in use.")

            self.__staff[staff.id] = staff
            self.__person_ids.add(staff.id)
            return staff

    def _find_conflicts(self, patient, staff, hour, ignore_appointment=None):
        """Return a list of active appointments conflicting with the patient or staff at that hour."""
        conflicts = []
        for appointment in self.__appointments.values():
            if appointment is ignore_appointment:
                continue

            if appointment.status == "CANCELLED":
                continue

            if appointment.start_hour == hour:
                if appointment.patient is patient or appointment.staff is staff:
                    conflicts.append(appointment)

        return conflicts

    def book_appointment(self, appointment_id, patient, staff, start_hour):
        with self._action(f"book appointment #{appointment_id}"):
            if appointment_id in self.__appointment_ids or appointment_id in self.__person_ids:
                raise DuplicateIDError(
                    f"ID {appointment_id} has already been used."
                )

            if patient.id not in self.__patients or self.__patients[patient.id] is not patient:
                raise BookingError("Patient is not registered with this clinic.")

            if staff.id not in self.__staff or self.__staff[staff.id] is not staff:
                raise BookingError("Staff member is not registered with this clinic.")

            conflicts = self._find_conflicts(patient, staff, start_hour)

            if conflicts:
                # Twist 1 (Emergency): If patient is flagged emergency, it can bump PENDING appointment(s)
                if patient.is_emergency:
                    # Check if any conflict is CONFIRMED
                    confirmed_conflicts = [c for c in conflicts if c.status == "CONFIRMED"]
                    if confirmed_conflicts:
                        raise BookingError(
                            "Emergency booking cannot bump a CONFIRMED appointment."
                        )

                    # All conflicts are PENDING: bump them
                    for conflicting in conflicts:
                        conflicting.cancel(self._clock.now(), reason="bumped")
                        print(
                            f"EMERGENCY BUMP: Appointment #{conflicting.id} "
                            f"({conflicting.patient.name} with {conflicting.staff.name}) was bumped."
                        )
                else:
                    raise BookingError(
                        "Booking conflict: patient or staff member already has an active appointment at that hour."
                    )

            appointment = Appointment(appointment_id, patient, staff, start_hour)
            self.__appointments[appointment_id] = appointment
            self.__appointment_ids.add(appointment_id)
            return appointment

    def _get_appointment(self, appointment_id):
        try:
            return self.__appointments[appointment_id]
        except KeyError:
            raise BookingError(
                f"Appointment #{appointment_id} does not exist."
            )

    def confirm_appointment(self, appointment_id):
        with self._action(f"confirm appointment #{appointment_id}"):
            appointment = self._get_appointment(appointment_id)
            appointment.confirm()
            return appointment

    def cancel_appointment(self, appointment_id, reason="cancelled"):
        with self._action(f"cancel appointment #{appointment_id}"):
            appointment = self._get_appointment(appointment_id)
            appointment.cancel(self._clock.now(), reason)
            return appointment

    def appointments(self):
        return tuple(
            self.__appointments[key]
            for key in sorted(self.__appointments)
        )

    def find_appointment(self, appointment_id):
        return self._get_appointment(appointment_id)

    def staff_members(self):
        return tuple(self.__staff.values())

    def patients(self):
        return tuple(self.__patients.values())


# ----------------------------- Polymorphism ----------------------------

def print_staff_fees(staff_members):
    """Each staff object provides its own role() and fee() implementation."""
    print("\nSTAFF FEES")
    for member in staff_members:
        print(f"{member.name} | {member.role()} | fee: ${member.fee():.2f}")
