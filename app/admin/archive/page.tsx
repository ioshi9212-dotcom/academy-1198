import { isAdmin } from "@/lib/admin";
import { formatDateTime, rub } from "@/lib/format";
import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";
import { restoreClient } from "../my-clients/actions";

export const dynamic = "force-dynamic";

const archivedBookingStatuses = ["CANCELLED_BY_CLIENT", "CANCELLED_BY_ADMIN", "REJECTED", "COMPLETED", "NO_SHOW"];

export default async function ArchivePage() {
  if (!isAdmin()) redirect("/admin/login");

  const [archivedClients, archivedBookings] = await Promise.all([
    prisma.client.findMany({
      where: { status: "REJECTED" },
      orderBy: { createdAt: "desc" }
    }),
    prisma.booking.findMany({
      where: { status: { in: archivedBookingStatuses as any } },
      include: { client: true, service: true },
      orderBy: { startAt: "desc" },
      take: 150
    })
  ]);

  return (
    <div className="grid">
      <section className="card">
        <div className="actions" style={{ justifyContent: "space-between" }}>
          <div>
            <h1>Архив</h1>
            <p>Здесь хранятся архивные клиенты и завершённые, отменённые, отклонённые записи. Данные не удаляются.</p>
          </div>
          <div className="actions">
            <a className="button secondary" href="/admin/my-clients">Мои клиенты</a>
            <a className="button secondary" href="/admin/manage">Ручная запись</a>
            <a className="button secondary" href="/admin">Админка</a>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Архивные клиенты</h2>
        {archivedClients.length === 0 ? <div className="notice">Архивных клиентов пока нет.</div> : null}
        <table className="table">
          <thead><tr><th>Клиент</th><th>Телефон</th><th>Заметки</th><th></th></tr></thead>
          <tbody>
            {archivedClients.map((client) => (
              <tr key={client.id}>
                <td>{client.lastName} {client.firstName}<br /><span className="small">ДР: {client.birthDate.toISOString().slice(0, 10)}</span></td>
                <td>{client.phone}</td>
                <td><pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>{client.notes}</pre></td>
                <td>
                  <form action={restoreClient}>
                    <input type="hidden" name="id" value={client.id} />
                    <button className="ok">Вернуть в активные</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Архив записей</h2>
        {archivedBookings.length === 0 ? <div className="notice">Архивных записей пока нет.</div> : null}
        <table className="table">
          <thead><tr><th>Дата</th><th>Клиент</th><th>Услуга</th><th>Статус</th><th>Комментарии</th></tr></thead>
          <tbody>
            {archivedBookings.map((booking) => (
              <tr key={booking.id}>
                <td>{formatDateTime(booking.startAt)}</td>
                <td>{booking.client.lastName} {booking.client.firstName}<br /><span className="small">{booking.client.phone}</span></td>
                <td>{booking.service.title}<br /><span className="small">{rub(booking.finalPrice ?? booking.service.price)}</span></td>
                <td><span className="status">{booking.status}</span></td>
                <td><b>Клиент:</b> {booking.clientComment || "—"}<br /><b>Мастер:</b> {booking.adminComment || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
