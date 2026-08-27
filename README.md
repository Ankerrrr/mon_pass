# Quant Home

Quant Home 是供可信任家用 LAN 使用的 Binance 現貨量化研究後端。本階段提供單一管理員登入、USDT 現貨交易對目錄、K 線下載與不可變資料集快取，以及受限併發背景工作。系統僅使用 Binance 公開市場資料，不保存 API key，也不會送出真實訂單。

## 啟動

需求：Docker Desktop（含 Docker Compose）。

1. 複製 `.env.example` 為 `.env`。
2. 至少更換 `QUANT_DB_PASSWORD` 與 `QUANT_HOME_INITIAL_ADMIN_PASSWORD`。
3. 執行：

   ```powershell
   docker compose up -d --build
   ```

API 啟動前會自動執行 Alembic migration。確認服務：

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

預期 health response：

```json
{"status":"ok","mode":"simulation"}
```

## LAN 存取

預設只綁定 `127.0.0.1`。若要讓同一可信任 LAN 的其他裝置連線，將 `.env` 的 `QUANT_HOME_BIND_HOST` 改為 `0.0.0.0`，並只在作業系統防火牆允許私人網路的 TCP 8000。請勿設定路由器 port forwarding，也不要把服務直接暴露到網際網路。

若透過 HTTPS reverse proxy 使用，設定 `QUANT_HOME_HTTPS_ENABLED=true`，使 session cookie 加上 `Secure`。

## 認證與 CSRF

- `POST /api/auth/login` 以 JSON 傳入 `username` 與 `password`。
- 登入後瀏覽器保存 HttpOnly、SameSite=Strict session cookie；資料庫只保存 token 摘要。
- login response 的 `csrf_token` 必須放入所有變更狀態請求的 `X-CSRF-Token` header。
- 除 `/api/health` 與登入外，應用端點都要求管理員 session。

初始管理員只在資料庫尚無管理員時建立。建立後修改 `.env` 密碼不會自動重設既有密碼。

## 測試與 migration

```powershell
docker compose run --rm api pytest -q
docker compose run --rm api alembic upgrade head
```

停止服務：

```powershell
docker compose down
```

資料庫保存在具名 volume `postgres-data`。只有在確定要永久清除所有資料時，才使用 `docker compose down -v`。
