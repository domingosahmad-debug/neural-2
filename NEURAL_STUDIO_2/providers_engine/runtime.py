"""Select actual execution capability from a server-admitted packet."""
from .transport import Transport
from .production_host import ProductionHost
from .gemini import GeminiTransport


class RuntimeTransport:
    def __init__(self):
        self.text = Transport()
        self.production = ProductionHost(timeout=3600)
        self.gemini = GeminiTransport()

    def supports(self, route, mode):
        return route in ('claude','codex','opencode','gemini')

    def run(self,row,packet,folder,session,cancel):
        if row.get('route') == 'gemini':
            if packet.get('toolMode') == 'production' and not packet.get('productionScope'):
                return {'status':'FAILED','error':'No server-issued production scope; no worker started.','execution_started':False}
            return self.gemini.run(row,packet,folder,session,cancel)
        if packet.get('toolMode') == 'production':
            if not packet.get('productionScope'):
                return {'status':'FAILED','error':'No server-issued production scope; no worker started.','execution_started':False}
            return self.production.run(row,packet,folder,session,cancel)
        return self.text.run(row,packet,folder,session,cancel)
