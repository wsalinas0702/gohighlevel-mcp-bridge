# GoHighLevel MCP Bridge

This repository contains a FastAPI application that acts as an MCP bridge between an OpenAI Agent and a GoHighLevel CRM sub-account.

## Features

- Manage contacts (create and update)
- Send SMS and email messages
- Manage pipeline opportunities (create and update)
- Schedule and list appointments
- Trigger campaigns and workflows

## Setup

1. Create a `.env` file based on `.env.example` and fill in your GoHighLevel API key and Location ID.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run the server using `uvicorn main:app --host 0.0.0.0 --port 8000`.
4. Deploy the service (e.g. on Render, Replit, Vercel).
5. Connect your OpenAI Agent by using the manifest URL: `https://<your-deployment-domain>/.well-known/ai-plugin.json`.

## License

MIT License
