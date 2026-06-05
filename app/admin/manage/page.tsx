import { isAdmin } from "@/lib/admin";
import { formatDateTime, rub } from "@/lib/format";
import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";
import { cancelManualBooking, createManualBooking, createManualClient, updateManualBooking, updateManualClient } from "./actions";

export const dynamic = "force-dynamic";

const clientStatuses = ["PENDING", "APPROVED", "REJECTED", "BANNED"];
const bookingStatuses = ["PENDING", "CONFIRMED", "CANCELLED_BY_CLIENT", "CANCELLED_BY_ADMIN", "REJECTED", "COMPLETED", "NO_SHOW"];

function toDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

function toDateTimeInput(date: Date) {
  return date.toISOString().slice(0, 16);
}

export default async function ManualAdminPage() {
  if (!isAdmin()) redirect("/admin/login");

  const [clients, services, bookings] = await Promise.all([
    prisma.client.findMany({ orderBy: [{ status: "asc" }, { createdAt: "desc" }] }),
    prisma.service.findMany({ orderBy: [{ isActive: "desc" }, { sortOrder: "asc" }, { title: "asc" }] }),
    prisma.booking.findMany({ include: { client: true, service: true }, orderBy: { startAt: "desc" }, take: 80 })
  ]);

  return (
    <div className="grid">
      <section className="card">
        <div className="actions" style={{ justifyContent: "space-between" }}>
          <div>
            <h1>Ручное управление</h1>
            <p>Добавление и редактирование клиентов, ручная запись, изменение записи и отмена.</p>
          </div>
          <a className="button secondary" href="/admin">Назад</a>
        </div>
      </section>

      <section className="card">
        <h2>Добавить клиента</h2>
        <form action={createManualClient} className="grid">
          <div className="grid-3">
            <label>Имя<input name="firstName" required /></label>
            <label>Фамилия<input name="lastName" required /></label>
            <label>Телефон<input name="phone" required placeholder="79XXXXXXXXX" /></label>
          </div>
          <div className="grid-3">
            <label>Дата рождения<input name="birthDate" type="date" required /></label>
            <label>Статус<select name="status" defaultValue="APPROVED">{clientStatuses.map((x) => <option key={x}>{x}</option>)}</select></label>
            <label>Заметка<input name="notes" /></label>
          </div>
          <button>Добавить</button>
        </form>
      </section>

      <section className="card">
        <h2>Записать клиента вручную</h2>
        {clients.length === 0 || services.length === 0 ? <div className="notice">Нужен хотя бы один клиент и одна услуга.</div> : (
          <form action={createManualBooking} className="grid">
            <div className="grid-3">
              <label>Клиент<select name="clientId">{clients.map((c) => <option key={c.id} value={c.id}>{c.lastName} {c.firstName} — {c.phone}</option>)}</select></label>
              <label>Услуга<select name="serviceId">{services.map((s) => <option key={s.id} value={s.id}>{s.title} — {s.durationMinutes} мин — {rub(s.price)}</option>)}</select></label>
              <label>Дата и время<input name="startAt" type="datetime-local" required /></label>
            </div>
            <div className="grid-3">
              <label>Статус<select name="status" defaultValue="CONFIRMED">{bookingStatuses.map((x) => <option key={x}>{x}</option>)}</select></label>
              <label>Итоговая цена<input name="finalPrice" type="number" min="0" /></label>
              <label>Комментарий клиента<input name="clientComment" /></label>
            </div>
            <label>Твоя заметка<textarea name="adminComment" /></label>
            <button>Создать запись</button>
          </form>
        )}
      </section>

      <section className="card">
        <h2>Клиенты</h2>
        <div className="notice">Удаление клиента пока не включала специально. Для нежелательных клиентов ставь статус BANNED.</div>
        <table className="table">
          <thead><tr><th>Данные</th><th>Статус</th><th>Заметки</th><th></th></tr></thead>
          <tbody>
            {clients.map((client) => (
              <tr key={client.id}>
                <td>
                  <form id={`client-${client.id}`} action={updateManualClient} className="grid">
                    <input type="hidden" name="id" value={client.id} />
                    <input name="lastName" defaultValue={client.lastName} required />
                    <input name="firstName" defaultValue={client.firstName} required />
                    <input name="phone" defaultValue={client.phone} required />
                    <input name="birthDate" type="date" defaultValue={toDateInput(client.birthDate)} required />
                  </form>
                </td>
                <td><select name="status" form={`client-${client.id}`} defaultValue={client.status}>{clientStatuses.map((x) => <option key={x}>{x}</option>)}</select></td>
                <td><textarea name="notes" form={`client-${client.id}`} defaultValue={client.notes} /></td>
                <td><button form={`client-${client.id}`} className="ok">Сохранить</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Записи</h2>
        <table className="table">
          <thead><tr><th>Дата/клиент</th><th>Услуга/статус</th><th>Цена/комментарии</th><th></th></tr></thead>
          <tbody>
            {bookings.map((booking) => (
              <tr key={booking.id}>
                <td>
                  <form id={`booking-${booking.id}`} action={updateManualBooking} className="grid">
                    <input type="hidden" name="id" value={booking.id} />
                    <input name="startAt" type="datetime-local" defaultValue={toDateTimeInput(booking.startAt)} required />
                    <select name="clientId" defaultValue={booking.clientId}>{clients.map((c) => <option key={c.id} value={c.id}>{c.lastName} {c.firstName} — {c.phone}</option>)}</select>
                    <span className="small">Сейчас: {formatDateTime(booking.startAt)}</span>
                  </form>
                </td>
                <td><div className="grid"><select name="serviceId" form={`booking-${booking.id}`} defaultValue={booking.serviceId}>{services.map((s) => <option key={s.id} value={s.id}>{s.title} — {s.durationMinutes} мин</option>)}</select><select name="status" form={`booking-${booking.id}`} defaultValue={booking.status}>{bookingStatuses.map((x) => <option key={x}>{x}</option>)}</select></div></td>
                <td><div className="grid"><input name="finalPrice" form={`booking-${booking.id}`} type="number" min="0" defaultValue={booking.finalPrice ?? ""} placeholder={String(booking.service.price)} /><input name="clientComment" form={`booking-${booking.id}`} defaultValue={booking.clientComment} /><textarea name="adminComment" form={`booking-${booking.id}`} defaultValue={booking.adminComment} /></div></td>
                <td className="actions"><button form={`booking-${booking.id}`} className="ok">Сохранить</button><form action={cancelManualBooking}><input type="hidden" name="id" value={booking.id} /><button className="danger">Отменить</button></form></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
