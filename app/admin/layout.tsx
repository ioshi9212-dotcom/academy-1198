export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid">
      <section className="card">
        <h2>Быстрое меню</h2>
        <div className="actions">
          <a className="button" href="/admin/my-clients">Мои клиенты</a>
          <a className="button secondary" href="/admin/archive">Архив</a>
          <a className="button secondary" href="/admin/manage">Ручная запись</a>
          <a className="button secondary" href="/admin/requests">Заявки клиентов</a>
          <a className="button secondary" href="/admin/bookings">Записи</a>
          <a className="button secondary" href="/admin/services">Прайс</a>
          <a className="button secondary" href="/admin/schedule">Расписание</a>
        </div>
      </section>
      {children}
    </div>
  );
}
