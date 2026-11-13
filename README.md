# a13n for AstrBot

[简体中文](README.zh-CN.md)

Run AstrBot text conversations on an existing [a13n Service](https://a13n.converge.ai/docs/a13n-service/) Agent. The plugin runs a loopback HTTP endpoint inside AstrBot. AstrBot’s built-in Dify Chat Runner calls that endpoint, and the plugin forwards messages to a13n. Install the plugin and configure the two components through AstrBot’s WebUI.

## Requirements

- AstrBot 4.29.4 with Python 3.12 or later. The plugin targets the 4.29 series starting at 4.29.4.
- A reachable a13n Service with the Threads, Inbox and Runs endpoints in its `/api/v1` API.
- A text-output Agent and a workspace API key whose principal has `read` and `run` access.

## Setup

1. In AstrBot WebUI, open **Extensions → Plugins**. Install this repository by URL if AstrBot can access it, or upload a ZIP of the plugin directory. With a private repository, download the ZIP while signed in to GitHub and upload it from your machine.
2. Open the plugin’s configuration and set the following fields. Save and reload the plugin.

   | Setting | Value |
   | --- | --- |
   | `service_url` | a13n Service base URL, with `/api/v1` omitted. Use an address reachable from AstrBot, including when it runs in Docker. |
   | `service_api_key` | a13n workspace API key. |
   | `agent_id` | ID of the a13n Agent that will run the conversations. |
   | `bridge_key` | A separate random key of at least 24 ASCII letters or digits. For example, generate one with `python -c "import secrets; print(secrets.token_hex(24))"`. |
   | `port` | Local HTTP port. The default is `18767`. |
   | `timeout_seconds` | Maximum time the plugin waits for a reply, including queue time. The default is `90`. |

3. In the AstrBot configuration profile for your bot, open **AI → More actions → Change execution mode**, select **Dify**, and enable AI. Set the application type to **Chat**, the API Base to `http://127.0.0.1:18767/v1` (adjust the port if needed), and the Dify API Key to the plugin’s **`bridge_key`**. Set the Dify timeout above the plugin timeout, for example **120 seconds**, and save. If AstrBot uses an HTTP proxy, put `127.0.0.1` in the AstrBot process’s `NO_PROXY` list.
4. Send a normal chat message, then ask a follow-up. Both turns should appear under the same a13n Thread. Use AstrBot’s `/reset` to start a fresh Thread on the next message.

## Conversations and limits

The plugin stores the link between Dify conversation IDs and a13n Thread IDs in AstrBot’s plugin data directory. Conversation scope follows the session ID AstrBot passes to Dify. Configure session isolation in AstrBot before enabling shared chats. Keep the plugin data directory to continue existing conversations after an update or restart.

The first version handles text. It sends the final a13n reply in Dify SSE format once the Run completes. Attachments, live text deltas, and approval or client-tool prompts are outside this version’s scope. A chat timeout or disconnect ends local observation. The remote Run can continue in a13n.

| Symptom | Check |
| --- | --- |
| Connection refused | Reload the plugin, check its startup log, and confirm the port matches the Dify API Base. |
| Invalid local bridge key | Copy `bridge_key` into the Dify API Key field. Keep the a13n workspace key in the plugin settings. |
| a13n denied access | Check that the workspace key can read and run the selected Agent. |
| Conversation unavailable | Run `/reset` after changing the service or Agent, or after replacing the plugin data directory. |
| Waiting or timed out | Open the Run in a13n to see its status and handle any pending interaction. |

## Verification

The integration was exercised with AstrBot 4.29.4's built-in Dify Runner on Python 3.12 and a local a13n Service using a scripted model. The first reply, a follow-up after plugin reload, and a fresh Thread after clearing the Dify conversation ID were checked. Automated tests also cover local authentication, session isolation, and retrying a submission with the same idempotency key.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Native Runner roadmap

The execution mode appears as **Dify** in AstrBot today. Once AstrBot ships the plugin registration API tracked in [Custom Agent Runner #9942](https://github.com/AstrBotDevs/AstrBot/issues/9942), the plan is to register an **a13n** execution mode from this plugin. The native Runner will reuse the a13n client and the existing conversation storage where session identities can be mapped. The release that adds the native Runner will document how to switch profiles and keep existing Threads.

## License

GNU Affero General Public License v3.0. This repository was created from the [AstrBot plugin template](https://github.com/Soulter/helloworld).
