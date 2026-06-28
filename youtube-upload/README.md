# YouTube API upload setup

This directory contains a local YouTube Data API v3 upload workflow.

## Files

- `youtube_oauth.py` — one-time OAuth helper.
- `youtube_upload.py` — dry-run and upload CLI.
- `config/client_secret.json` — Google OAuth Desktop client credentials; ignored by git.
- `config/youtube_token.json` — default profile OAuth token/refresh token; ignored by git.
- `config/tokens/<profile>_token.json` — named profile OAuth token/refresh token for additional YouTube accounts/channels; ignored by git.
- `config/tokens/<profile>_pending.json` — temporary OAuth state created by `auth-url` before `exchange`; ignored by git.

## One-time Google Cloud setup

1. Create/select a Google Cloud project:
   https://console.cloud.google.com/projectselector2/home/dashboard
2. Enable YouTube Data API v3:
   https://console.cloud.google.com/apis/library/youtube.googleapis.com
3. Configure OAuth consent screen. If app is in Testing, add your Google account as a test user:
   https://console.cloud.google.com/auth/audience
4. Create OAuth 2.0 Client ID:
   https://console.cloud.google.com/apis/credentials
   - Application type: Desktop app
   - Download JSON file

## Local authorization

Default profile, stored at `config/youtube_token.json`:

```bash
cd C:/Project/Beauty-Video-Transport/youtube-upload
python youtube_oauth.py auth-url --client-secret config/client_secret.json
```

Named profile for an additional account/channel, stored at `config/tokens/<profile>_token.json`:

```bash
cd C:/Project/Beauty-Video-Transport/youtube-upload
python youtube_oauth.py auth-url --profile profile1 --client-secret config/client_secret.json
```

Open the printed `auth_url`, approve access with the intended YouTube/Google account, then copy the full redirected URL from the address bar. If the browser shows a localhost connection error after approval, that is expected; copy that failed `http://localhost:8080/?code=...` URL.

Exchange the code:

```bash
# default profile
python youtube_oauth.py exchange "http://localhost:8080/?code=..."
python youtube_upload.py check-auth
python youtube_upload.py list-channels

# named profile
python youtube_oauth.py exchange --profile profile1 "http://localhost:8080/?code=..."
python youtube_upload.py check-auth --profile profile1
python youtube_upload.py list-channels --profile profile1
```

## Dry run

```bash
python youtube_upload.py dry-run \
  --profile profile1 \
  --file 'C:/Project/Beauty-Video-Transport/outputs/真顶-BV1WgEk63EKa-no-ending.mp4' \
  --title '真顶' \
  --description 'Source: Bilibili / UP: 逝者如是乎 / BV1WgEk63EKa' \
  --tags 'shorts,bilibili' \
  --privacyStatus private
```

Omit `--profile profile1` to use the default profile.

## Upload

Only run after explicit user approval:

```bash
python youtube_upload.py upload \
  --profile profile1 \
  --file 'C:/Project/Beauty-Video-Transport/outputs/真顶-BV1WgEk63EKa-no-ending.mp4' \
  --title '真顶' \
  --description 'Source: Bilibili / UP: 逝者如是乎 / BV1WgEk63EKa' \
  --tags 'shorts,bilibili' \
  --privacyStatus private
```

Omit `--profile profile1` to upload with the default profile.

## Important YouTube API limits

- Requires OAuth; API keys cannot upload videos.
- `videos.insert` supports resumable upload and requires scope `https://www.googleapis.com/auth/youtube.upload`.
- Unverified API projects created after 2020-07-28 may have uploaded videos restricted to private until the project passes YouTube API compliance review.
- Keep `config/*.json` secret; they contain credentials/tokens.
