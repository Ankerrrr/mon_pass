# Quant Home

Quant Home 是供可信任家用 LAN 使用的 Binance 現貨量化研究工作台。包含三策略回測、版本化設定、結果匯出、即時模擬交易、緊急停止、健康監控與稽核紀錄。系統僅使用 Binance 公開市場資料，不保存 API key，也不會送出真實訂單。

## 啟動

需求：Docker Desktop（含 Docker Compose）。

1. 複製 `.env.example` 為 `.env`。
2. 至少更換 `QUANT_DB_PASSWORD` 與 `QUANT_HOME_INITIAL_ADMIN_PASSWORD`。
3. 執行：

   ```powershell
   docker compose up -d --build
   ```

API 啟動前會自動執行 Alembic migration。瀏覽器開啟 [http://127.0.0.1:3000](http://127.0.0.1:3000)，確認服務：

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

預期 health response：

```json
{"status":"ok","mode":"simulation"}
```

## LAN 存取

預設只綁定 `127.0.0.1`。若要讓同一可信任 LAN 的其他裝置連線，先設定非預設的 `QUANT_HOME_INITIAL_ADMIN_PASSWORD`，再將 `.env` 的 `QUANT_HOME_BIND_HOST` 改為 `0.0.0.0`；若密碼仍是 placeholder，應用會拒絕啟動。作業系統防火牆只應允許私人網路的 TCP 3000（Web）與需要時的 8000（API）。請勿設定路由器 port forwarding，也不要把服務直接暴露到網際網路。

若透過 HTTPS reverse proxy 使用，設定 `QUANT_HOME_HTTPS_ENABLED=true`，使 session cookie 加上 `Secure`。

## 認證與 CSRF

- `POST /api/auth/login` 以 JSON 傳入 `username` 與 `password`。
- 登入後瀏覽器保存 HttpOnly、SameSite=Strict session cookie；資料庫只保存 token 摘要。
- login response 的 `csrf_token` 必須放入所有變更狀態請求的 `X-CSRF-Token` header。
- 除 `/api/health` 與登入外，應用端點都要求管理員 session。

`.env` 的管理員帳號與密碼是本機單一管理員的權威設定；修改後執行 `docker compose restart api` 即會同步，並使舊登入工作階段失效。

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

## 備份與還原

```powershell
.\scripts\backup.ps1 -Destination C:\QuantHomeBackups
.\scripts\restore.ps1 -BackupPath C:\QuantHomeBackups\quant-home-YYYYMMDD-HHMMSS
```

還原前必須輸入 `RESTORE`，且腳本會先建立一份還原前備份。
