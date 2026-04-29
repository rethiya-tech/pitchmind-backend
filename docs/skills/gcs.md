# GCS Storage Skill

## SDK
google-cloud-storage — NOT boto3, NOT S3 SDK

## Auth
Service account JSON key.
Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
OR set GCS_CREDENTIALS_JSON config field.

## Upload flow (browser → GCS direct)
1. Frontend calls POST /uploads/presign → { upload_url, gcs_key }
2. Frontend PUTs file directly to upload_url (no backend involved)
3. Frontend calls POST /uploads/confirm → { upload_id }
4. Backend verifies blob exists in GCS, saves upload row, runs parser

## Signed URL for upload (PUT)
```python
blob.generate_signed_url(
    version="v4",
    expiration=timedelta(minutes=15),
    method="PUT",
    content_type=content_type)
```
Content-Type must match what frontend sends in PUT header.

## Signed URL for download (GET)
```python
blob.generate_signed_url(
    version="v4",
    expiration=timedelta(hours=1),
    method="GET")
```

## Upload bytes from backend (for PPTX)
```python
blob.upload_from_string(pptx_bytes,
    content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
```

## Key naming
uploads/    → uploads/{user_id}/{uuid}.{ext}
pptx/       → pptx/{conversion_id}.pptx

## CORS (set once in GCP Console)
```json
[{"origin": ["https://your-app.vercel.app"],
  "method": ["PUT", "GET"],
  "responseHeader": ["Content-Type"],
  "maxAgeSeconds": 3600}]
```
Apply: gsutil cors set cors.json gs://pitchmind-files

## Frontend direct upload
```ts
const { data } = await api.post("/uploads/presign", {
  filename, content_type: file.type, size_bytes: file.size })
await axios.put(data.upload_url, file, {
  headers: { "Content-Type": file.type },
  onUploadProgress: e => setProgress(e.loaded / e.total * 100)
})
await api.post("/uploads/confirm", {
  gcs_key: data.gcs_key, filename, file_size_bytes: file.size,
  mime_type: file.type })
```
