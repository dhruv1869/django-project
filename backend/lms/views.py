from django.http import HttpResponse

def index(request):
    return HttpResponse("LMS API is working ")
