# Frontend

Next.js app for the Vulcan OmniPro 220 multimodal assistant.

## Phase 1 status

The frontend is intentionally still a scaffold, but it now exposes the real product direction instead of the default create-next-app starter:

- challenge-branded landing shell
- quick actions for common welding workflows
- reserved surfaces for chat, evidence, source viewing, and artifacts

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Next milestones

- wire SSE chat streaming from the FastAPI backend
- add source cards and evidence viewer
- render diagrams, calculators, and troubleshooting artifacts
- support image upload for weld and machine-photo workflows
