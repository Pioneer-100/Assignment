from clinic import (
    Clinic, ManualClock, Patient, Doctor, Nurse, Pharmacist,
    MedicalLecturer, Person, ClinicError, print_staff_fees
)

# Student ID: r2420373 -> P = 2420373
# P mod 5 = 3 -> Doctor fee: 40 + 5 * 3 = $55.00
# P mod 3 = 0 -> Nurse fee:  10 + 0     = $10.00
# Pharmacist fee: fixed at               $5.00
# P mod 4 = 1 -> Twist: Emergency Booking
P_VALUE = 2420373


def show_appointments(clinic):
    print("\nCURRENT APPOINTMENTS")
    for appointment in clinic.appointments():
        reason_str = f" (Reason: {appointment.cancellation_reason})" if appointment.status == "CANCELLED" else ""
        print(
            f"  #{appointment.id}: {appointment.patient.name} with "
            f"{appointment.staff.name}, hour {appointment.start_hour}, "
            f"status={appointment.status}{reason_str}"
        )


def attempt(label, action):
    """Run one demonstration action and display expected rule failures cleanly."""
    print(f"\n--- {label} ---")
    try:
        action()
    except ClinicError as error:
        print(f"EXPECTED FAILURE: {error}")


def main():
    print("CLINIC APPOINTMENT SYSTEM")
    print("=========================")
    print(f"Configured P = {P_VALUE}")
    print(f"P mod 5 = {P_VALUE % 5} (Doctor fee: ${40 + 5 * (P_VALUE % 5)})")
    print(f"P mod 3 = {P_VALUE % 3} (Nurse fee: ${10 + (P_VALUE % 3)})")
    print(f"P mod 4 = {P_VALUE % 4} (Twist: Emergency booking)\n")

    # The clock is injected. No direct computer-clock access is used.
    clock = ManualClock(10)
    clinic = Clinic(clock, "appointment_log.txt")

    # 1. Register patients
    alice = Patient("Alice", 101, "student")
    brian = Patient("Brian", 102, "visitor")
    carol = Patient("Carol", 103, "staff-member")
    david = Patient("David", 104, "visitor")
    emily = Patient("Emily (Emergency)", 105, "visitor", is_emergency=True)

    for patient in (alice, brian, carol, david, emily):
        clinic.register_patient(patient)

    # 2. Register staff
    doctor = Doctor("Dr Smith", 201, P_VALUE)
    nurse = Nurse("Nurse Grace", 202, P_VALUE)
    pharmacist = Pharmacist("Mr James", 203)

    for member in (doctor, nurse, pharmacist):
        clinic.register_staff(member)

    # Q3: Polymorphism (Single loop over staff with no instanceof/isinstance)
    print_staff_fees(clinic.staff_members())

    # Patient roles and discount policy
    print("\nPATIENTS")
    for patient in clinic.patients():
        emerg_tag = " [EMERGENCY FLAGGED]" if patient.is_emergency else ""
        print(
            f"{patient.name} | {patient.role()} | "
            f"type={patient.patient_type} | pays {patient.payment_rate() * 100:.0f}%{emerg_tag}"
        )

    # Q5: Diamond inheritance and Person constructor count
    print("\nMULTIPLE INHERITANCE DEMONSTRATION")
    before = Person.constructor_calls
    medical_lecturer = MedicalLecturer(
        "Dr Moyo", 301, "Health Informatics", P_VALUE
    )
    after = Person.constructor_calls
    print(f"Name: {medical_lecturer.name}")
    print(f"Role: {medical_lecturer.role()}")
    print(f"Module: {medical_lecturer.module_name}")
    print(f"Fee: ${medical_lecturer.fee():.2f}")
    print(f"Person constructor calls for this object: {after - before}")
    print(f"MedicalLecturer MRO: {[cls.__name__ for cls in MedicalLecturer.mro()]}")

    # Standard booking & confirmation
    print("\nBOOKING APPOINTMENTS")
    first = clinic.book_appointment(1, alice, doctor, 15)
    clinic.confirm_appointment(first.id)
    print(f"Booked appointment #{first.id}: {first.status}")
    print(f"Alice's appointment price: ${first.price():.2f} (Student 50% discount on ${doctor.fee():.2f})")

    # Regular pending booking
    second = clinic.book_appointment(2, brian, doctor, 16)
    print(f"Booked appointment #{second.id}: {second.status}")

    # A deliberate conflict: Non-emergency patient cannot double-book staff at hour 16
    attempt(
        "Deliberate non-emergency conflict at hour 16",
        lambda: clinic.book_appointment(3, david, doctor, 16)
    )

    # Twist 1 (Emergency): Emergency patient Emily bumps Brian's PENDING appointment at hour 16
    print("\n--- EMERGENCY BUMPING PENDING APPOINTMENT ---")
    emergency_appt = clinic.book_appointment(4, emily, doctor, 16)
    print(f"Emergency appointment #{emergency_appt.id} booked at hour 16!")
    print(f"Original appointment #{second.id} status now: {second.status} (Reason: '{second.cancellation_reason}')")

    # Deliberate Failure: Emergency patient cannot bump a CONFIRMED appointment (appointment #1 at hour 15)
    frank_emergency = Patient("Frank (Emergency)", 106, "visitor", is_emergency=True)
    clinic.register_patient(frank_emergency)
    attempt(
        "Deliberate attempt for emergency patient to bump a CONFIRMED appointment at hour 15",
        lambda: clinic.book_appointment(5, frank_emergency, doctor, 15)
    )

    # Cancellation rules
    print("\nCANCELLATION RULES DEMONSTRATION")
    # Valid cancellation (hour 10, start 15 -> 5 hours before start)
    cancelled = clinic.cancel_appointment(1, "patient requested cancellation")
    print(f"Appointment #1 cancelled successfully. Status: {cancelled.status}")

    # Attempt to cancel an already cancelled appointment
    attempt(
        "Deliberate attempt to cancel an already cancelled appointment",
        lambda: clinic.cancel_appointment(1, "trying again")
    )

    # Late cancellation: less than 2 hours before start for confirmed
    later = clinic.book_appointment(10, david, nurse, 20)
    clinic.confirm_appointment(later.id)
    clock.set_hour(19)  # 1 hour before start
    attempt(
        "Deliberate late cancellation (only 1 hour before start for confirmed)",
        lambda: clinic.cancel_appointment(10, "too late")
    )

    # Cancellation after appointment start
    clock.set_hour(20)  # At appointment start hour
    attempt(
        "Deliberate cancellation after appointment start",
        lambda: clinic.cancel_appointment(10, "already started")
    )

    # Duplicate appointment ID
    attempt(
        "Deliberate duplicate appointment ID",
        lambda: clinic.book_appointment(1, carol, pharmacist, 25)
    )

    # Valid booking with pharmacist
    clinic.book_appointment(11, carol, pharmacist, 25)

    show_appointments(clinic)

    print("\nDEMO COMPLETE")
    print("Check appointment_log.txt for successful and failed actions.")
    print("Each action prints [log] opened and [log] closed.")


if __name__ == "__main__":
    main()
