from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from store.workspaces import landing_redirect

from . import services
from .forms import DriverLoginForm, FailDeliveryForm
from .models import Delivery, Driver


def driver_required(view):
    """Нэвтэрсэн + идэвхтэй Driver профайлтай хэрэглэгч л орно. request.driver-д хадгална."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('delivery:login')}?next={request.path}")
        driver = Driver.objects.filter(user=request.user, is_active=True).select_related('user').first()
        if driver is None:
            messages.error(request, 'Энэ бүртгэл хүргэгчийн эрхгүй байна.')
            return redirect('delivery:login')
        request.driver = driver
        return view(request, *args, **kwargs)

    return wrapper


def login_view(request):
    if request.user.is_authenticated and Driver.objects.filter(user=request.user, is_active=True).exists():
        return redirect('delivery:board')

    form = DriverLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        next_url = request.POST.get('next') or request.GET.get('next') or ''
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        # A person who is also an admin (two positions) picks which site to open.
        return landing_redirect(form.get_user())
    return render(request, 'delivery/login.html', {'form': form, 'next': request.GET.get('next', '')})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('delivery:login')


@driver_required
def dashboard(request):
    driver = request.driver
    today = timezone.localdate()
    mine = Delivery.objects.filter(driver=driver)

    stats = mine.aggregate(
        waiting=Count('id', filter=Q(status__in=[Delivery.ASSIGNED, Delivery.ACCEPTED])),
        moving=Count('id', filter=Q(status__in=[Delivery.PICKED_UP, Delivery.ON_THE_WAY])),
        done=Count('id', filter=Q(status=Delivery.DELIVERED, delivered_at__date=today)),
    )
    stats['total'] = stats['waiting'] + stats['moving'] + stats['done']

    active = mine.filter(status__in=Delivery.ACTIVE_STATUSES).select_related('order').order_by('assigned_at')
    return render(request, 'delivery/dashboard.html', {'driver': driver, 'stats': stats, 'deliveries': active})


@driver_required
def deliveries(request):
    flt = request.GET.get('f', 'active')
    qs = Delivery.objects.filter(driver=request.driver).select_related('order')
    if flt == 'active':
        qs = qs.filter(status__in=Delivery.ACTIVE_STATUSES).order_by('assigned_at')
    elif flt == 'done':
        qs = qs.filter(status__in=[Delivery.DELIVERED, Delivery.FAILED]).order_by('-id')
    else:
        flt = 'all'
        qs = qs.order_by('-id')
    return render(request, 'delivery/deliveries.html', {'driver': request.driver, 'deliveries': qs[:100], 'flt': flt})


@driver_required
def detail(request, pk):
    # Зөвхөн өөрт оноогдсон хүргэлт. Бусдынх нь 404.
    delivery = get_object_or_404(
        Delivery.objects.select_related('order').prefetch_related('order__items'),
        pk=pk, driver=request.driver,
    )
    ctx = {
        'driver': request.driver,
        'delivery': delivery,
        'items': delivery.order.items.all(),
        'fail_form': FailDeliveryForm(),
        'history': delivery.history.select_related('driver__user')[:20],
    }
    return render(request, 'delivery/detail.html', ctx)


@driver_required
@require_POST
def action(request, pk, name):
    if name not in services.ACTIONS:
        raise Http404
    reason = note = ''
    if name == 'fail':
        form = FailDeliveryForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Амжилтгүй болсон шалтгаанаа сонгоно уу.')
            return redirect('delivery:detail', pk=pk)
        reason, note = form.cleaned_data['reason'], form.cleaned_data['note']

    try:
        services.advance(pk, request.driver, name, reason=reason, note=note)
    except Delivery.DoesNotExist:
        raise Http404
    except services.DeliveryError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, {
            'accept': 'Хүргэлтийг хүлээн авлаа.',
            'pickup': 'Барааг авсан гэж тэмдэглэлээ.',
            'depart': 'Хүргэлтэнд гарлаа.',
            'deliver': 'Хүргэлт амжилттай дууслаа.',
            'fail': 'Хүргэлт амжилтгүй гэж тэмдэглэгдлээ.',
        }[name])
    return redirect('delivery:detail', pk=pk)


@driver_required
def profile(request):
    driver = request.driver
    if request.method == 'POST':
        driver.is_online = request.POST.get('is_online') == '1'
        driver.save(update_fields=['is_online'])
        driver.refresh_status()
        messages.success(request, 'Төлөв шинэчлэгдлээ.')
        return redirect('delivery:profile')
    done = Delivery.objects.filter(driver=driver, status=Delivery.DELIVERED).count()
    return render(request, 'delivery/profile.html', {'driver': driver, 'done_total': done})


# ---------------------------------------------------------------------------
# 3 үе шаттай самбар (нэг хуудас, товч дарахад зөвхөн самбарын хэсэг шинэчлэгдэнэ)
# ---------------------------------------------------------------------------

def _board_context(driver):
    services.ensure_deliveries()
    mine = Delivery.objects.filter(driver=driver).select_related('order').prefetch_related('order__items')
    today = timezone.localdate()
    pool = (Delivery.objects.filter(status=Delivery.PENDING, driver__isnull=True)
            .select_related('order').prefetch_related('order__items').order_by('created_at'))
    to_receive = list(mine.filter(status=Delivery.ASSIGNED).order_by('assigned_at'))
    to_depart = list(mine.filter(status=Delivery.PICKED_UP).order_by('picked_up_at'))
    onway = mine.filter(status=Delivery.ON_THE_WAY).order_by('on_the_way_at')
    to_unload = [d for d in onway if d.unloaded_at is None]      # 2-р үе: буулгах
    to_confirm = [d for d in onway if d.unloaded_at is not None]  # 3-р үе: батлах (бүгд буусан үед л нээгдэнэ)
    return {
        'driver': driver,
        'pool_count': pool.count(),
        'to_receive': to_receive,
        'pool': pool,
        'to_depart': to_depart,
        'to_unload': to_unload,
        'to_confirm': to_confirm,
        'unloaded_n': len(to_confirm),
        'onway_total': len(to_unload) + len(to_confirm),
        'receive_n': pool.count() + len(to_receive),
        'step2_n': len(to_depart) + len(to_unload),
        'current_step': 2 if (to_depart or to_unload) else (3 if to_confirm else 1),
        'done_today': mine.filter(status=Delivery.DELIVERED, delivered_at__date=today).count(),
        'failed_today': mine.filter(status=Delivery.FAILED, failed_at__date=today).count(),
        'fail_form': FailDeliveryForm(),
    }


def _render_board(request):
    return render_to_string('delivery/_board.html', _board_context(request.driver), request=request)


@driver_required
def board(request):
    # Самбарын контекстийг шууд board.html-д өгнө ({% include %} хийнэ), урьдчилж render хийсэн string биш.
    return render(request, 'delivery/board.html', _board_context(request.driver))


@driver_required
def board_partial(request):
    return JsonResponse({'ok': True, 'html': _render_board(request)})


@driver_required
@require_POST
def board_action(request, step):
    """step: receive | depart | unload | confirm. Хариу нь JSON: {ok, message, html}."""
    driver = request.driver
    try:
        if step == 'receive':
            n = services.receive_from_warehouse(driver, request.POST.getlist('ids'))
            msg = f'{n} захиалгыг агуулхаас авлаа.'
        elif step == 'depart':
            n = services.depart(driver, request.POST.getlist('ids'))
            msg = f'{n} захиалгатай замд гарлаа. Хүргэж өгсөн барааг сонгож буулгана уу.'
        elif step == 'unload':
            n = services.unload(driver, request.POST.getlist('ids'))
            left = services.pending_unload_count(driver)
            msg = (f'{n} захиалгын барааг буулгалаа. Үлдсэн: {left}.' if left
                   else f'{n} захиалгын барааг буулгалаа. Бүх бараа буулаа - одоо хүргэснийг батална уу.')
        elif step == 'confirm':
            result = request.POST.get('result', 'deliver')
            reason = note = ''
            if result == 'fail':
                form = FailDeliveryForm(request.POST)
                if not form.is_valid():
                    raise services.DeliveryError('Амжилтгүй болсон шалтгаанаа сонгоно уу.')
                reason, note = form.cleaned_data['reason'], form.cleaned_data['note']
            d = services.confirm_by_order_id(driver, request.POST.get('order_id'), result, reason, note)
            msg = (f'Захиалга #{d.order_id} хүргэгдсэн гэж батлагдлаа.' if result == 'deliver'
                   else f'Захиалга #{d.order_id} амжилтгүй гэж тэмдэглэгдлээ.')
            if not Delivery.objects.filter(driver=driver, status__in=Delivery.ACTIVE_STATUSES).exists():
                msg += ' Бүх хүргэлт батлагдлаа - та шинэ хүргэлтэнд гарахад бэлэн боллоо.'
        else:
            raise Http404
    except services.DeliveryError as exc:
        return JsonResponse({'ok': False, 'message': str(exc), 'html': _render_board(request)}, status=400)
    return JsonResponse({'ok': True, 'message': msg, 'html': _render_board(request)})