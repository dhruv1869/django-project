from django.http import HttpResponse

def index(request):
    return HttpResponse("User API is working ")
