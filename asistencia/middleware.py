class DatosPrivadosMiddleware:
    """No almacenar páginas de cuentas, QR o registros personales en cachés compartidas."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith('/static/'):
            response['Cache-Control'] = 'private, no-store'
        return response
