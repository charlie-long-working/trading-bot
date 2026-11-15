# Trading-bot — hướng dẫn cho agent

- Skill: `.cursor/skills/trading-bot/` (repo map) và `.cursor/skills/crypto-oi-usdtd/` (OI playbook). Codex đọc `.agents/skills/…`, Claude Code đọc `.claude/skills/…` — symlink về cùng thư mục. Repo tổng `Documents/Cursor/.cursor/skills/{trading-bot,crypto-oi-usdtd}` cũng là symlink về đây: **chỉ sửa bản trong repo này**.
- Tổng quan: `README.md`, `docs/ARCHITECTURE.md`. Workspace: `../AGENTS.md`.
- Do not extend `archive/`.
- Prefer updating `docs/ARCHITECTURE.md` when adding SoT modules or entrypoints.
- Repo **public**: không commit `.env`, khoá API.
- `stock`, `precious-metals`, `real-estate` import code từ `botdown/` và `data_loaders/` — đổi tên/chữ ký hàm thì sửa cả các repo đó.
- Trạng thái 15/11/2026: workflow OI alerts `disabled_inactivity`; cảnh báo kịch bản K lỗi HTML khi gửi Telegram (chi tiết trong skill `trading-bot`).
