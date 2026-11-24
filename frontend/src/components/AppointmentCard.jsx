export default function AppointmentCard({ bookingRef, start, clinician }) {
  return (
    <article className="card appointment" aria-label="Appointment confirmed">
      <div className="card-tag">✓ Appointment confirmed</div>
      <h2>{start}</h2>
      <p>with <strong>{clinician}</strong></p>
      <div className="ref">
        <span>Booking reference</span>
        <code>{bookingRef}</code>
      </div>
      <p className="note">Keep this reference to cancel or change the appointment.</p>
    </article>
  );
}
