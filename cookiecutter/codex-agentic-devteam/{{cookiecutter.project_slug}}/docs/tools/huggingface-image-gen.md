# Hugging Face görsel üretim scripti

Codex ile kullanıma uygun, tek dosyalık HF görsel üretici. Bulut Inference API
(token ile) veya yerel `diffusers` (GPU/VRAM ile) yolunu destekler.

## Kurulum

```bash
pip install huggingface_hub diffusers torch accelerate pillow
```

## Kullanım

```bash
# Bulut API (varsayılan) — token gerekir
export HF_TOKEN="huggingface_tokenınız"
python generate_image.py "A futuristic city at sunset, cyberpunk style"

# Yerel model (GPU gerekir)
python generate_image.py "A futuristic city at sunset" --local

# Model / çıktı override
python generate_image.py "..." --model black-forest-labs/FLUX.1-schnell --output out.png
```

Token: https://huggingface.co/settings/tokens

Script dosyası: `generate_image.py` (bu scaffold'ın kökünde, aynı dizinde).

## Notlar / test durumu

- **Doğrulanmış:** `black-forest-labs/FLUX.1-schnell` bulut yolunda çalışıyor (1024×1024
  üretim). `stabilityai/stable-diffusion-2-1` gibi eski modeller **404 / "no inference
  provider mapping"** verir — HF eski serverless Inference API'yi bırakıp **"Inference
  Providers"** (fal/replicate/together…) modeline geçti; eski SD modelleri bir sağlayıcıya
  bağlı değil. **Doğru varsayılan: FLUX.1-schnell** (FLUX.1-dev de olur). Gerekirse
  `client.text_to_image(..., provider="...")` ile sağlayıcı belirtilebilir.
- **Bulut yolu (varsayılan):** `HF_TOKEN` + `huggingface_hub` + ağ gerektirir. Bir model
  "warm" değilse ilk çağrıda 503/model-loading dönebilir; tekrar denemek gerekir.
- **Yerel yol (`--local`):** `torch_dtype=torch.float16` + `enable_model_cpu_offload()`
  CUDA (NVIDIA GPU) varsayar. Apple Silicon (MPS) veya CPU'da bunlar uyarlanmalı
  (float32 / `pipe.to("mps")`), yoksa hata verir.

## Pitfalls (bilinen sorunlar → çözüm)

1. **Eski SD modelleri 404 verir.** `stabilityai/stable-diffusion-2-1` (ve çoğu klasik SD)
   → `RepositoryNotFoundError: 404 ... no inference provider mapping`. HF, eski serverless
   Inference API'yi bırakıp **Inference Providers** (fal/replicate/together…) modeline geçti;
   bu modeller bir sağlayıcıya bağlı değil. **Çözüm:** `black-forest-labs/FLUX.1-schnell`
   (veya FLUX.1-dev) kullan; gerekirse `text_to_image(..., provider="...")`.
2. **`pip install` macOS'ta bloklanır (PEP 668).** Homebrew Python "externally-managed";
   düz `pip install` reddedilir. **Çözüm:** venv (`python3 -m venv .venv && .venv/bin/pip
   install huggingface_hub pillow`) ya da bilinçli `--break-system-packages`. **Not:** bulut
   yolu için sadece `huggingface_hub` + `pillow` yeter (genelde zaten kurulu).
3. **`--local` yalnızca CUDA varsayar.** `float16` + `enable_model_cpu_offload()` NVIDIA
   içindir. Apple Silicon'da: `diffusers` kur, `float32` + `pipe.to("mps")`. CPU çok yavaş.
4. **`timeout` komutu macOS'ta yok** (coreutils `gtimeout`). Sarmalayıcı scriptlerde ona
   güvenme; Python tarafı zaten kendi timeout'unu uygular.
5. **Token güvenliği.** Token'ı **sohbete yapıştırma** — loglanır, ifşa sayılır, **iptal et**.
   Gitignore'lu `.env`'de tut (`HF_TOKEN=...`), `set -a; . ./.env; set +a` ile yükle.
   `InferenceClient()` `HF_TOKEN`'ı ortamdan otomatik okur — açıkça geçmeye gerek yok.
   Token'ı asla bir dosyaya yazma/commit etme.
6. **Model "cold start"** → geçerli ama soğuk model ilk çağrıda 503 dönebilir; tekrar dene.
7. **Sağlayıcı kotası/ücreti** — FLUX (providers üzerinden) kredi/kota tüketebilir; ücretsiz
   pay sınırlıdır.

## Bu araca dair değişiklik kaydı

Bu doküman ve `generate_image.py` yeni bir projeye adapte edildiğinde, o projenin kendi
patch/değişiklik kaydına (varsa `docs/patches/PATCH_REGISTRY.md` gibi bir dosyaya) kendi
tarih/commit referanslarınızla not düşün — bu scaffold kopyası kasıtlı olarak repo-özel
geçmiş kayıtlarından arındırılmıştır.
