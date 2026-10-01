import "./app.css";

const navigationItems = ["Аккаунты", "Доноры", "Мои каналы", "Связи", "Входящие"];

export const App = () => (
  <div className="app-shell">
    <aside className="sidebar">
      <p className="eyebrow">NEWSFLOW</p>
      <h1>Content Studio</h1>
      <nav aria-label="Основная навигация">
        {navigationItems.map((item) => (
          <a href={`#${item}`} key={item}>{item}</a>
        ))}
      </nav>
    </aside>
    <main className="workspace">
      <p className="eyebrow">TELEGRAM NEWS HUB</p>
      <h2>Входящие материалы</h2>
      <p>Новые публикации появятся здесь после подключения источников.</p>
      <section className="safe-mode" aria-label="Режим публикации">
        <strong>Режим модерации включён</strong>
        <span>Автопубликация отключена до Dry Run и явного подтверждения.</span>
      </section>
    </main>
  </div>
);
