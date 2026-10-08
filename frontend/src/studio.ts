export type Page =
  | "overview"
  | "inbox"
  | "donors"
  | "channels"
  | "connections"
  | "planner"
  | "accounts"
  | "settings";
export type Tone = "blue" | "green" | "orange" | "violet" | "red" | "muted";
export type ContentState =
  "Новый" | "На проверке" | "Готово" | "Отклонён" | "Удалён у донора";
export type Post = {
  id: string;
  source: string;
  title: string;
  original: string;
  suggestion: string;
  draft: string;
  state: ContentState;
  time: string;
  art: string;
  destinations: string[];
  editorial: "PASS" | "REJECT" | "PENDING";
  rewriteAllowed: boolean;
  revision: number;
  sourceDeleted?: boolean;
};
export type Donor = {
  id: string;
  name: string;
  category: string;
  art: string;
  state: string;
  enabled: boolean;
  daily: number;
  synced: string;
  words: string;
  media: string;
};
export type Channel = {
  id: string;
  name: string;
  category: string;
  art: string;
  subscribers: string;
  daily: number;
  today: number;
  mode: string;
  quietStart: string;
  quietEnd: string;
  windowStart: string;
  windowEnd: string;
  profile: string;
};
export type Route = {
  id: string;
  donorId: string;
  channelId: string;
  intake: number;
  mix: number;
  policy: string;
  enabled: boolean;
  text: boolean;
  photo: boolean;
};
export type Account = {
  id: string;
  name: string;
  phone: string;
  state: string;
  donors: number;
  channels: number;
  synced: string;
};
export type ScheduledPost = {
  id: string;
  postId: string;
  date: string;
  time: string;
  channelId: string;
};

export const navigation: { id: Page; label: string; description: string }[] = [
  {
    id: "overview",
    label: "Обзор",
    description: "Поток контента от источников до публикации",
  },
  {
    id: "inbox",
    label: "Входящие",
    description: "Новые материалы из источников для проверки и публикации",
  },
  {
    id: "donors",
    label: "Доноры",
    description: "Управление источниками контента из Telegram",
  },
  {
    id: "channels",
    label: "Мои каналы",
    description: "Настройки публикаций и правил ваших Telegram-каналов",
  },
  {
    id: "connections",
    label: "Связи",
    description: "Настройте, как материалы доноров попадают в ваши каналы",
  },
  {
    id: "planner",
    label: "Планировщик",
    description: "Планируйте публикации и управляйте очередью материалов",
  },
  {
    id: "accounts",
    label: "Аккаунты",
    description: "Подключённые сессии Telegram для работы с контентом",
  },
  {
    id: "settings",
    label: "Настройки",
    description: "Параметры рабочего пространства, модерации и публикации",
  },
];

export function createDemo() {
  const posts: Post[] = [
    {
      id: "mars",
      source: "Наука сегодня",
      title: "На Марсе обнаружены следы древних рек",
      original:
        "Группа учёных изучила снимки высохших долин Марса. По мнению исследователей, вода могла сохраняться там значительно дольше, чем предполагалось ранее. На снимках видны долины и разветвлённые каналы, похожие на высохшие русла рек.\n\nИсследователи продолжают анализировать данные. Новые наблюдения помогут уточнить историю воды на планете.",
      suggestion:
        "Новые снимки Марса показали древние русла рек. Учёные уточняют, как долго на планете могла сохраняться вода.",
      draft: "",
      state: "Новый",
      time: "12:24",
      art: "mars",
      destinations: ["tech", "facts"],
      editorial: "PASS",
      rewriteAllowed: true,
      revision: 1,
    },
    {
      id: "model",
      source: "Технологии и люди",
      title: "Новые инструменты для разработчиков",
      original:
        "Исследовательская команда представила инструменты для анализа программного кода. В демонстрации показали поиск ошибок и совместную работу.",
      suggestion: "",
      draft: "",
      state: "На проверке",
      time: "11:47",
      art: "tech",
      destinations: ["tech"],
      editorial: "PASS",
      rewriteAllowed: true,
      revision: 1,
    },
    {
      id: "cats",
      source: "Котики и наука",
      title: "Почему кошки мурлыкают",
      original:
        "Исследование рассматривает разные причины мурлыканья домашних кошек. Авторы наблюдали животных в нескольких ситуациях.",
      suggestion: "",
      draft: "",
      state: "Готово",
      time: "10:32",
      art: "cat",
      destinations: ["curious"],
      editorial: "PASS",
      rewriteAllowed: true,
      revision: 1,
    },
    {
      id: "forest",
      source: "Зелёная планета",
      title: "В Европе запустили проект по восстановлению лесов",
      original:
        "Несколько регионов объединили усилия для восстановления лесных массивов и защиты редких видов.",
      suggestion: "",
      draft: "",
      state: "Новый",
      time: "09:18",
      art: "forest",
      destinations: ["world"],
      editorial: "PASS",
      rewriteAllowed: true,
      revision: 1,
    },
    {
      id: "galaxy",
      source: "Космос ближе",
      title: "Новый взгляд на формирование галактик",
      original:
        "Астрономы сравнили наблюдения удалённых галактик с результатами моделирования.",
      suggestion: "",
      draft: "",
      state: "На проверке",
      time: "Вчера",
      art: "space",
      destinations: ["facts"],
      editorial: "PENDING",
      rewriteAllowed: false,
      revision: 1,
    },
    {
      id: "reject",
      source: "Тестовый источник",
      title: "Материал отклонён редакторским фильтром",
      original:
        "Синтетический материал для проверки запрета обработки после EditorialGate REJECT.",
      suggestion: "",
      draft: "",
      state: "Отклонён",
      time: "Вчера",
      art: "tech",
      destinations: ["tech"],
      editorial: "REJECT",
      rewriteAllowed: false,
      revision: 1,
    },
  ];
  const donors: Donor[] = [
    {
      id: "@science_today",
      name: "Наука сегодня",
      category: "Наука",
      art: "space",
      state: "Активен",
      enabled: true,
      daily: 12,
      synced: "12:24",
      words: "Реклама, криптовалюта",
      media: "Текст и фото",
    },
    {
      id: "@tech_today",
      name: "Технологии и люди",
      category: "Технологии",
      art: "tech",
      state: "Активен",
      enabled: true,
      daily: 8,
      synced: "11:47",
      words: "Реклама",
      media: "Текст и фото",
    },
    {
      id: "@green_world",
      name: "Зелёная планета",
      category: "Природа",
      art: "forest",
      state: "На проверке",
      enabled: true,
      daily: 4,
      synced: "09:18",
      words: "",
      media: "Текст и фото",
    },
    {
      id: "@cosmos_near",
      name: "Космос ближе",
      category: "Космос",
      art: "space",
      state: "На паузе",
      enabled: false,
      daily: 6,
      synced: "Вчера",
      words: "",
      media: "Только текст",
    },
    {
      id: "@cats_science",
      name: "Котики и наука",
      category: "Факты",
      art: "cat",
      state: "Активен",
      enabled: true,
      daily: 5,
      synced: "10:32",
      words: "",
      media: "Текст и фото",
    },
    {
      id: "@world_nature",
      name: "Природа мира",
      category: "Природа",
      art: "mountain",
      state: "Активен",
      enabled: true,
      daily: 3,
      synced: "08:41",
      words: "",
      media: "Текст и фото",
    },
  ];
  const channels: Channel[] = [
    {
      id: "tech",
      name: "Технологии сегодня",
      category: "Технологии",
      art: "mountain",
      subscribers: "124 320",
      daily: 12,
      today: 8,
      mode: "Ручной",
      quietStart: "23:00",
      quietEnd: "08:00",
      windowStart: "09:00",
      windowEnd: "20:00",
      profile: "Нейтральный, без домыслов",
    },
    {
      id: "curious",
      name: "Это интересно",
      category: "Образование",
      art: "sun",
      subscribers: "89 441",
      daily: 8,
      today: 4,
      mode: "Ручной",
      quietStart: "00:00",
      quietEnd: "07:00",
      windowStart: "09:00",
      windowEnd: "20:00",
      profile: "Краткий",
    },
    {
      id: "facts",
      name: "Научные факты",
      category: "Наука",
      art: "atom",
      subscribers: "56 213",
      daily: 6,
      today: 3,
      mode: "Ручной",
      quietStart: "22:00",
      quietEnd: "08:00",
      windowStart: "09:00",
      windowEnd: "20:00",
      profile: "Нейтральный, без домыслов",
    },
    {
      id: "world",
      name: "Мир вокруг нас",
      category: "Природа",
      art: "forest",
      subscribers: "28 441",
      daily: 5,
      today: 2,
      mode: "Ручной",
      quietStart: "22:00",
      quietEnd: "08:00",
      windowStart: "09:00",
      windowEnd: "20:00",
      profile: "Краткий",
    },
  ];
  const routes: Route[] = [
    {
      id: "science-facts",
      donorId: donors[0].id,
      channelId: "facts",
      intake: 68,
      mix: 42,
      policy: "С проверкой",
      enabled: true,
      text: true,
      photo: true,
    },
    {
      id: "tech-tech",
      donorId: donors[1].id,
      channelId: "tech",
      intake: 75,
      mix: 60,
      policy: "Только вручную",
      enabled: true,
      text: true,
      photo: true,
    },
    {
      id: "green-world",
      donorId: donors[2].id,
      channelId: "world",
      intake: 40,
      mix: 30,
      policy: "С проверкой",
      enabled: false,
      text: true,
      photo: false,
    },
  ];
  const accounts: Account[] = [
    {
      id: "work",
      name: "Рабочий",
      phone: "+7 9•• ••• •• 42",
      state: "Активен",
      donors: 3,
      channels: 2,
      synced: "Сегодня, 12:24",
    },
    {
      id: "editor",
      name: "Редакция",
      phone: "+7 9•• ••• •• 18",
      state: "Активен",
      donors: 2,
      channels: 1,
      synced: "Сегодня, 11:47",
    },
    {
      id: "content",
      name: "Контент",
      phone: "+7 9•• ••• •• 91",
      state: "Ожидает входа",
      donors: 0,
      channels: 0,
      synced: "Вчера, 16:24",
    },
    {
      id: "archive",
      name: "Архив",
      phone: "+7 9•• ••• •• 26",
      state: "Ошибка",
      donors: 0,
      channels: 0,
      synced: "Вчера, 21:03",
    },
    {
      id: "test",
      name: "Тестовый",
      phone: "+7 9•• ••• •• 11",
      state: "Требует 2FA",
      donors: 1,
      channels: 1,
      synced: "Вчера, 09:18",
    },
  ];
  const scheduled: ScheduledPost[] = [
    {
      id: "model-tech",
      postId: "model",
      date: "2026-09-29",
      time: "11:00",
      channelId: "tech",
    },
    {
      id: "cats-curious",
      postId: "cats",
      date: "2026-10-01",
      time: "15:00",
      channelId: "curious",
    },
  ];
  return { posts, donors, channels, routes, accounts, scheduled };
}
export type StudioData = ReturnType<typeof createDemo>;
export const demoWeekStart = "2026-09-28"; // Fixed, explicitly labelled fixture period; Monday.
// Calendar cards occupy 128px at 48px/hour; group their visual intersections.
export function calendarSlots(jobs: ScheduledPost[]) {
  const slots: { minute: number; end: number; jobs: ScheduledPost[] }[] = [];
  for (const job of [...jobs].sort(
    (a, b) => a.time.localeCompare(b.time) || a.id.localeCompare(b.id),
  )) {
    const minute =
      Number(job.time.slice(0, 2)) * 60 + Number(job.time.slice(3));
    const prior = slots.at(-1);
    if (prior && minute < prior.end) {
      prior.jobs.push(job);
      prior.end = minute + 160;
    } else slots.push({ minute, end: minute + 160, jobs: [job] });
  }
  return slots;
}
export function datePlus(date: string, days: number) {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}
export function canProcess(post: Post) {
  return (
    !post.sourceDeleted &&
    post.state !== "Удалён у донора" &&
    post.editorial === "PASS" &&
    post.rewriteAllowed &&
    post.state !== "Отклонён"
  );
}
const clockTime = /^(?:[01]\d|2[0-3]):[0-5]\d$/;
export function channelSettingsError(channel: Channel) {
  if (
    ![
      channel.windowStart,
      channel.windowEnd,
      channel.quietStart,
      channel.quietEnd,
    ].every((time) => clockTime.test(time)) ||
    channel.windowStart >= channel.windowEnd
  )
    return "Проверьте окно публикации и тихие часы.";
  if (!Number.isInteger(channel.daily) || channel.daily < 1)
    return "Дневной лимит должен быть положительным целым числом.";
  return "";
}
export function scheduleError(
  post: Post | undefined,
  channel: Channel | undefined,
  date: string,
  time: string,
) {
  if (post?.sourceDeleted || post?.state === "Удалён у донора")
    return "Источник удалён у донора. Планирование запрещено.";
  if (!post || !canProcess(post))
    return "Материал не прошёл EditorialGate. Планирование запрещено.";
  if (!channel) return "Выберите канал.";
  const invalidChannel = channelSettingsError(channel);
  if (invalidChannel) return invalidChannel;
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(date) ||
    !clockTime.test(time) ||
    Number.isNaN(new Date(`${date}T12:00:00Z`).valueOf()) ||
    new Date(`${date}T12:00:00Z`).toISOString().slice(0, 10) !== date
  )
    return "Укажите корректные дату и время.";
  if (time < channel.windowStart || time >= channel.windowEnd)
    return "Время находится вне окна публикации канала.";
  const quiet =
    channel.quietStart <= channel.quietEnd
      ? time >= channel.quietStart && time < channel.quietEnd
      : time >= channel.quietStart || time < channel.quietEnd;
  return quiet ? "Время попадает в тихие часы канала." : "";
}
export function stateTone(state: string): Tone {
  if (["Активен", "Готово"].includes(state)) return "green";
  if (["Ошибка", "Отклонён"].includes(state)) return "red";
  if (["Новый", "Требует 2FA"].includes(state)) return "violet";
  if (["На проверке", "Ожидает входа"].includes(state)) return "orange";
  return "muted";
}

export function validateDonors(raw: string, existing: string[]) {
  const seen = new Set(existing.map((id) => id.toLowerCase()));
  return raw
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line) => {
      const value = line
        .trim()
        .replace(/^https?:\/\/(?:www\.)?t\.me\//i, "")
        .replace(/^@/, "");
      const id = `@${value.toLowerCase()}`;
      const error = !/^[a-zA-Z][a-zA-Z0-9_]{3,31}$/.test(value)
        ? "Неверный username"
        : seen.has(id)
          ? "Дубликат"
          : "";
      if (!error) seen.add(id);
      return { input: line.trim(), id, error };
    });
}
