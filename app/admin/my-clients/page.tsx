import { isAdmin } from "@/lib/admin";
import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";
import { archiveClient, saveMyClient } from "./actions";

export const dynamic = "force-dynamic";

const activeStatuses = ["PENDING", "APPROVED", "BANNED"];
const statuses = ["PENDING", "APPROVED", "BANNED", "REJECTED"];

function toDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

export default async function MyClientsPage() {
  if (!isAdmin()) redirect("/admin/login");

  const clients = await prisma.client.findMany({
    where: { status: { in: activeStatuses as any } },
    orderBy: [{ status: "asc" }, { createdAt: "desc" }]
  });

  return (
    <section className="card">
      <div className="actions" style={{ justifyContent: "space-between" }}>
        <div>
          <h1>Мои клиенты</h1>
          <p>Активная клиентская база. Здесь можно редактировать данные клиента и отправлять клиента в архив.</p>
        </div>
        <div className="actions">
          <a className="button secondary" href="/admin/manage">Ручная запись</a>
          <a className="button secondary" href="/admin/archive">Архив</a>
          <a className="button secondary" href="/admin">Админка</a>
        </div>
      </div>

      <table className="table">
        <thead><tr><th>Клиент</th><th>Контакты/статус</th><th>Заметки</th><th>Архив</th></tr></thead>
        <tbody>
          {clients.map((client) => (
            <tr key={client.id}>
              <td>
                <form id={`client-${client.id}`} action={saveMyClient} className="grid">
                  <input type="hidden" name="id" value={client.id} />
                  <input name="lastName" defaultValue={client.lastName} required />
                  <input name="firstName" defaultValue={client.firstName} required />
                  <input name="birthDate" type="date" defaultValue={toDateInput(client.birthDate)} required />
                </form>
              </td>
              <td>
                <div className="grid">
                  <input name="phone" form={`client-${client.id}`} defaultValue={client.phone} required />
                  <select name="status" form={`client-${client.id}`} defaultValue={client.status}>
                    {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
                  </select>
                  <span className="small">Создан: {client.createdAt.toLocaleDateString("ru-RU")}</span>
                </div>
              </td>
              <td><textarea name="notes" form={`client-${client.id}`} defaultValue={client.notes} /></td>
              <td className="actions">
                <button form={`client-${client.id}`} className="ok">Сохранить</button>
                <form action={archiveClient} className="grid">
                  <input type="hidden" name="id" value={client.id} />
                  <input name="archiveReason" placeholder="причина архива" />
                  <button className="danger">В архив</button>
                </form>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
