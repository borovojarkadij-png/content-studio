# Research and reuse matrix

| Project | License | Useful ideas | Decision |
| --- | --- | --- | --- |
| Telethon | MIT | Async MTProto, events, media, FloodWait errors | Use as dependency only |
| Telegram-C2C | Unverified for reuse review | Basic source/target filtering | Do not reuse code |
| Generic Telegram forwarders | Mixed/unclear | Product inspiration only | Do not reuse code |
| YouTube Data API | Google API terms | Metadata/OAuth/quota-aware future adapter | Use official API later |

Forwarder scripts do not supply the required durable state, hard editorial
boundary, idempotency, scheduling, or recovery model. License verification is
required before any third-party code is copied.
