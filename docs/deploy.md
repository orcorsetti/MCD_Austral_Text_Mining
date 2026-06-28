# Deploy para testing (tunnel desde tu máquina)

Expone la app a internet por **un solo puerto**, usando tu GPU + LM Studio locales.
El frontend compilado se sirve desde la misma API (FastAPI), así que solo se tunelea el `:8000`.

## Pasos

1. **Compilar el frontend** (una vez por cambio de UI):
   ```bash
   cd frontend && npm run build
   ```
   Genera `frontend/dist`, que FastAPI sirve en `/` (ver `app/api.py`).

2. **Levantar el backend** (env `ldi2_cuda`, desde la raíz):
   ```bash
   uvicorn app.api:app --port 8000
   ```
   Sirve el frontend en `/` y la API en `/api/*` en el mismo origen.

3. **(Opcional) LM Studio** sirviendo `qwen/qwen3.6-27b` en `:1234` para las explicaciones.

4. **Tunnel público** (cloudflared quick tunnel, sin cuenta):
   ```bash
   tools/cloudflared.exe tunnel --url http://localhost:8000
   ```
   Imprime una URL `https://<aleatorio>.trycloudflare.com` → esa es la que se comparte.

## Notas

- **URL efímera:** cambia cada vez que reinicias `cloudflared`. Para una URL fija hace falta
  una cuenta de Cloudflare + named tunnel.
- **Sin autenticación:** cualquiera con el link puede usar la app (corre sobre tu GPU/LLM). Cortá
  el tunnel para cerrar el acceso.
- **Tu máquina debe quedar prendida** mientras dure el test.
- `tools/` (el binario de cloudflared) está gitignored. Bajarlo de nuevo:
  `https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe`
- Para un deploy permanente sin tu máquina: frontend estático (Vercel) + backend en cloud
  (CPU o GPU) bajando los embeddings de HuggingFace, y `LLM_EXPLANATIONS=0` o un LLM hosteado.
