"""LLM provider seam for ACO agents (Foundry Local today, Azure later).

No tkinter, no pip. Every provider implements:

* ``name`` — stable id (``foundry_local``, ``azure_foundry``, ``none``)
* ``available()`` → bool
* ``generate(prompt, system=None, timeout=…)`` → text or raises

The ERP never talks to Azure SDKs from the domain core — Phase C wires an
HTTP adapter here (same pattern as ``foundry_client``). Until configured,
``azure_foundry`` reports unavailable with a plain-language reason.
"""

import foundry_client

# App-settings keys (optional). Absent = local-only.
SETTING_PROVIDER = 'ai_provider'          # foundry_local | azure_foundry | auto
SETTING_AZURE_ENDPOINT = 'azure_foundry_endpoint'
SETTING_AZURE_DEPLOYMENT = 'azure_foundry_deployment'
# API key is *never* stored in SQLite by this module — read from env only when
# Phase C is enabled: ACO_AZURE_FOUNDRY_KEY.


class ProviderError(Exception):
    pass


def _setting(conn, key, default=''):
    if conn is None:
        return default
    try:
        row = conn.execute(
            'SELECT value FROM app_settings WHERE key = ?', (key,)
        ).fetchone()
        return (row['value'] if row and row['value'] is not None else default) or default
    except Exception:  # noqa: BLE001
        return default


class FoundryLocalProvider:
    name = 'foundry_local'

    def available(self, timeout=0.8):
        return foundry_client.available(timeout=timeout)

    def generate(self, prompt, system=None, timeout=60):
        return foundry_client.generate(
            prompt, system=system, timeout=timeout)


class AzureFoundryProvider:
    """Opt-in Azure AI Foundry / Azure OpenAI-compatible chat endpoint.

    Config: ``app_settings.azure_foundry_endpoint`` (base URL) +
    ``azure_foundry_deployment`` (model/deployment name) + env
    ``ACO_AZURE_FOUNDRY_KEY``. Uses stdlib ``urllib`` only — same shape as
    Foundry Local's OpenAI-compatible API.
    """

    name = 'azure_foundry'

    def __init__(self, endpoint='', deployment='', api_key=''):
        self.endpoint = (endpoint or '').rstrip('/')
        self.deployment = deployment or ''
        self.api_key = api_key or ''

    def available(self, timeout=0.8):
        if not (self.endpoint and self.deployment and self.api_key):
            return False
        # Soft probe — many Azure endpoints need a POST to verify; we only
        # check that config is complete so ask() can try generate.
        return True

    def reason_unavailable(self):
        missing = []
        if not self.endpoint:
            missing.append('azure_foundry_endpoint setting')
        if not self.deployment:
            missing.append('azure_foundry_deployment setting')
        if not self.api_key:
            missing.append('ACO_AZURE_FOUNDRY_KEY env')
        return 'Azure Foundry not configured ({})'.format(
            ', '.join(missing) or 'unknown')

    def generate(self, prompt, system=None, timeout=60):
        if not self.available():
            raise ProviderError(self.reason_unavailable())
        import json
        import urllib.error
        import urllib.request
        # Azure OpenAI-style path; Foundry Agents HTTP will share this seam.
        url = (
            self.endpoint
            + '/openai/deployments/'
            + self.deployment
            + '/chat/completions?api-version=2024-06-01'
        )
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        body = json.dumps({
            'messages': messages,
            'temperature': 0.0,
        }).encode('utf-8')
        req = urllib.request.Request(
            url, data=body, method='POST',
            headers={
                'Content-Type': 'application/json',
                'api-key': self.api_key,
            })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            choices = data.get('choices') or []
            if not choices:
                raise ProviderError('Azure Foundry returned no choices')
            return (choices[0].get('message') or {}).get('content') or ''
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                'Azure Foundry call failed: {}'.format(exc)) from exc


class NoneProvider:
    name = 'none'

    def available(self, timeout=0.8):
        return False

    def generate(self, prompt, system=None, timeout=60):
        raise ProviderError('No AI provider available')


def resolve(conn=None, prefer=None):
    """Pick a provider.

    ``prefer`` / setting: ``foundry_local`` | ``azure_foundry`` | ``auto``
    (default). ``auto`` tries Azure if fully configured, else Foundry Local.
    """
    import os
    pref = (prefer or _setting(conn, SETTING_PROVIDER, 'auto') or 'auto').strip().lower()
    azure = AzureFoundryProvider(
        endpoint=_setting(conn, SETTING_AZURE_ENDPOINT),
        deployment=_setting(conn, SETTING_AZURE_DEPLOYMENT),
        api_key=os.environ.get('ACO_AZURE_FOUNDRY_KEY', ''),
    )
    local = FoundryLocalProvider()

    if pref == 'none':
        return NoneProvider()
    if pref == 'azure_foundry':
        return azure if azure.available() else NoneProvider()
    if pref == 'foundry_local':
        return local if local.available() else NoneProvider()
    # auto
    if azure.available():
        return azure
    if local.available():
        return local
    return NoneProvider()


def status(conn=None):
    """Machine-readable provider status for ``GET /api/agents/provider``."""
    import os
    azure = AzureFoundryProvider(
        endpoint=_setting(conn, SETTING_AZURE_ENDPOINT),
        deployment=_setting(conn, SETTING_AZURE_DEPLOYMENT),
        api_key=os.environ.get('ACO_AZURE_FOUNDRY_KEY', ''),
    )
    local = FoundryLocalProvider()
    active = resolve(conn)
    return {
        'active': active.name,
        'setting': _setting(conn, SETTING_PROVIDER, 'auto') or 'auto',
        'foundry_local': {
            'available': local.available(),
            'installed_cli': foundry_client.installed(),
            'model': foundry_client.DEFAULT_MODEL,
        },
        'azure_foundry': {
            'configured': bool(
                azure.endpoint and azure.deployment
                and os.environ.get('ACO_AZURE_FOUNDRY_KEY')),
            'available': azure.available(),
            'endpoint_set': bool(azure.endpoint),
            'deployment': azure.deployment or None,
            'reason': None if azure.available() else azure.reason_unavailable(),
            'phase': 'C',
            'note': (
                'Opt-in. Set app_settings + ACO_AZURE_FOUNDRY_KEY. '
                'Agents still only propose; ERP writes stay draft/confirm.'
            ),
        },
    }


def summarize(conn, agent, question, tool_results, knowledge, timeout=60):
    """Generate a narrative via the active provider, or None if offline."""
    import json
    provider = resolve(conn)
    if provider.name == 'none' or not provider.available():
        return None, 'none'
    system = (
        'You are the {name} for an Indian construction ERP (ACO). '
        'Use ONLY the tool JSON and knowledge snippets. Be concise. '
        'If data is missing, say so. Never invent rupees or dates. '
        'Remind that money/date actions need human approval.'
    ).format(name=agent['name'])
    prompt = (
        'Question: {q}\n\nKnowledge:\n{k}\n\nTool results (JSON):\n{t}\n\n'
        'Write 3–8 short sentences for the {audience}.'
    ).format(
        q=question or '',
        k='\n'.join('- ' + s['text'] for s in knowledge) or '(none)',
        t=json.dumps(tool_results, default=str)[:6000],
        audience=agent.get('audience') or 'user',
    )
    try:
        text = provider.generate(prompt, system=system, timeout=timeout)
        return (text or None), provider.name
    except Exception:  # noqa: BLE001
        return None, provider.name
