# Git Agents (gaj)

Агентная система для цикла разработки на GitHub: Code Agent (Issue → PR), AI Reviewer (ревью PR), генерация README по структуре проекта. Работа через Issues, Pull Requests и при необходимости GitHub Actions.

---

## Как запустить локально

### 1. Клонировать и перейти в папку

```bash
git clone https://github.com/jylikt/bot-git-itmo.git
cd bot-git-itmo
```

### 2. Создать виртуальное окружение и установить зависимости

```bash
python -m venv .venv
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (CMD):** `.venv\Scripts\activate.bat`  
**Linux / macOS:** `source .venv/bin/activate`

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Настроить переменные окружения

Скопировать пример и заполнить:

```bash
cp .env.example .env
```

В `.env` обязательно указать:

| Переменная | Описание |
|------------|----------|
| `GITHUB_TOKEN` | [Personal Access Token](https://github.com/settings/tokens) с правами **repo** |
| `GITHUB_REPOSITORY` | Целевой репозиторий в формате `владелец/репо` (для code и reviewer) |
| `OPENROUTER_API_KEY` | Ключ с [OpenRouter](https://openrouter.ai/) (если используете OpenRouter) |

Для YandexGPT: `LLM_PROVIDER=yandexgpt`, `YC_FOLDER_ID`, `YC_API_KEY` или `YC_IAM_TOKEN`.

### 4. Запускать команды

Из корня проекта (с активированным `.venv`):

```bash
gaj code --issue 1
gaj reviewer --pr 2 --issue 1
gaj readme --repo-path https://github.com/owner/repo.git
```

Подробная пошаговая инструкция: [ИНСТРУКЦИЯ.md](ИНСТРУКЦИЯ.md).

---

## Команды и флаги

Единая точка входа — **`gaj`** и подкоманда.

### `gaj code` — Code Agent (Issue → код → PR)

Читает Issue, планирует изменения через LLM, клонирует репо (или использует кеш), вносит правки, пушит ветку и создаёт Pull Request.

| Флаг | Описание |
|------|----------|
| `--issue N` | **Обязательный.** Номер Issue в целевом репо. |
| `--pr N` | Номер существующего PR: доработать по замечаниям ревьюера (повторная итерация). |
| `--repo-path PATH` | Локальный путь к репо; иначе клон по `GITHUB_REPOSITORY` в кеш. |
| `--verbose`, `-v` | Вывести в stderr заголовок и тело Issue перед запросом к LLM. |
| `--no-cache` | Не использовать кеш клонов; каждый раз клонировать во временную папку. |

**Примеры:**
```bash
gaj code --issue 5
gaj code --issue 5 --pr 12
gaj code --issue 5 -v --no-cache
```

---

### `gaj reviewer` — Reviewer Agent (ревью PR)

Анализирует изменения в PR, сверяет с описанием Issue и результатами CI, пишет комментарий в PR. При замечаниях может добавить метку `agent-fix-requested`.

| Флаг | Описание |
|------|----------|
| `--pr N` | **Обязательный.** Номер Pull Request. |
| `--issue N` | **Обязательный.** Номер связанного Issue (для контекста требований). |
| `--ci-summary "текст"` | Краткое описание результатов CI (по умолчанию берётся из env `CI_SUMMARY`). |

**Пример:**
```bash
gaj reviewer --pr 8 --issue 5 --ci-summary "ruff ok, pytest passed"
```

---

### `gaj readme` — генерация README.md

Генерирует README по структуре и конфигам проекта (pyproject.toml, package.json, Dockerfile и т.д.). Определяет тип проекта (приложение или библиотека) и пишет разделы: клонирование, установка, запуск или использование.

| Флаг | Описание |
|------|----------|
| `--repo-path PATH \| URL` | Локальная папка или URL репо (например `https://github.com/owner/repo.git`). По умолчанию — текущая папка или клон по `GITHUB_REPOSITORY`. |
| `--output FILE` | Файл для записи. По умолчанию: `generate-readme/<название_репо>/README.md` в текущей папке. |
| `--dry-run` | Вывести текст README в stdout, не записывать в файл. |

**Примеры:**
```bash
gaj readme
gaj readme --repo-path https://github.com/jylikt/bot-git-itmo.git
gaj readme --repo-path ./my-project --output generate-readme/my-project/README.md
gaj readme --dry-run
```

---

## Кеш клонов

Для **`gaj code`** (и при необходимости для **`gaj readme`** без локальной папки) репозиторий клонируется в `.agent_cache/<владелец>_<репо>`. При следующих запусках кеш обновляется (`git fetch` + `git reset --hard origin/main`). Каталог кеша можно задать через `AGENT_CACHE_DIR`. Отключить кеш: **`gaj code --no-cache`**.

---

## Docker

```bash
docker build -t coding-agents .
docker run --rm -e GITHUB_TOKEN -e OPENROUTER_API_KEY -e GITHUB_REPOSITORY coding-agents code --issue 1
docker-compose run --rm code-agent --issue 1
docker-compose run --rm reviewer-agent --pr 1 --issue 1
```

В образе используется entrypoint для Code Agent; для reviewer вызывается `python -m coding_agents.cli_reviewer`.

---

## GitHub Actions

В репозитории настроены workflow:

- **Code Agent on Issue** — при открытии Issue (или метке `agent`) запускается Code Agent.
- **Code Agent on Fix Requested** — при метке `agent-fix-requested` на PR — новая итерация правок.
- **CI and Reviewer** — при открытии/обновлении PR: ruff, black, pytest и AI Reviewer.

В настройках репо нужны секреты: `OPENROUTER_API_KEY` (или YandexGPT). `GITHUB_TOKEN` выдаётся автоматически.

---

## Тесты и линтеры

```bash
ruff check src/
black src/
pytest tests/ -v
```

---

## Структура проекта

- `src/coding_agents/` — пакет агентов
- `src/coding_agents/cli.py` — единая точка входа `gaj` (code, reviewer, readme)
- `src/coding_agents/llm/` — провайдеры LLM (OpenRouter, YandexGPT)
- `.github/workflows/` — workflow для Issue, PR и Reviewer

Привет ИТМО