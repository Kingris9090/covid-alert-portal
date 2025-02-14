from django.views.generic import ListView, FormView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import logout
from django.utils.translation import gettext as _
from django.db.models import Q

from django_otp import devices_for_user
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken

from portal.mixins import Is2FAMixin, ProvinceAdminMixin, GetUserAdminMixin

from backup_codes.forms import RequestBackupCodesForm
from profiles.models import HealthcareUser
from announcements.models import Announcement

from django.conf import settings


class BackupCodeListView(Is2FAMixin, ListView):
    template_name = "backup_codes/backup_codes_list.html"
    context_object_name = "backup_code_list"

    def get(self, request, *args, **kwargs):
        if not get_user_static_device(self.request.user):
            return redirect(
                reverse_lazy("user_profile", kwargs={"pk": request.user.id})
            )

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        _recreate_backup_codes(request.user)
        return redirect(reverse_lazy("backup_codes"))

    def get_queryset(self):
        return _get_backup_codes_list(self.request.user)


class AdminBackupCodeListView(Is2FAMixin, ProvinceAdminMixin, ListView):
    template_name = "backup_codes/admin_backup_codes_list.html"
    context_object_name = "backup_code_list"

    def dispatch(self, request, *args, **kwargs):
        # setting self.staff_user so that other methods will have access to it
        self.staff_user = get_object_or_404(HealthcareUser, pk=self.kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if not get_user_static_device(self.staff_user):
            return redirect(
                reverse_lazy("user_profile", kwargs={"pk": self.staff_user.pk})
            )

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        _recreate_backup_codes(self.staff_user, num_codes=1)
        return redirect(
            reverse_lazy("backup_codes_admin", kwargs={"pk": self.staff_user.pk})
        )

    def get_queryset(self, *args, **kwargs):
        return get_user_static_device(self.staff_user).token_set.all()


class SignupBackupCodeListView(LoginRequiredMixin, ListView):
    template_name = "backup_codes/signup_backup_codes_list.html"
    context_object_name = "backup_code_list"

    def get(self, request, *args, **kwargs):
        # make sure you are coming from the /signup-2fa page
        if request.headers.get("Referer") and request.headers["Referer"].endswith(
            str(reverse_lazy("signup_2fa"))
        ):
            _recreate_backup_codes(request.user)
            return super().get(request, *args, **kwargs)

        return redirect(reverse_lazy("start"))

    # this is called _after_ self.get()
    def get_queryset(self):
        return _get_backup_codes_list(self.request.user)


class RequestBackupCodes(GetUserAdminMixin, LoginRequiredMixin, FormView):
    form_class = RequestBackupCodesForm
    template_name = "backup_codes/backup_codes_help.html"
    success_url = reverse_lazy("login_2fa")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add the currently logged user to the form
        kwargs["user"] = self.request.user
        kwargs["admin"] = self.user_admin
        return kwargs

    def form_valid(self, form):
        is_valid = super().form_valid(form)
        if is_valid:
            if settings.DEBUG:
                print(
                    f"DEBUG ONLY: Email message would have been sent to {form.admin.email} for {form.user.name} with {form.user.email} email address"
                )
            else:
                form.send_mail(self.request.LANGUAGE_CODE)

            logout(self.request)
            return redirect(reverse_lazy("backup_codes_contacted"))
        return is_valid


######################
# Utility functions used only by this module
######################


def _get_backup_codes_list(user):
    """Returns a fixed-length list filled with as many active backup codes as the user still has."""
    tokens = get_user_static_device(user).token_set.all()

    # create an array of a fixed size and fill it with as many tokens as actually exist
    token_list = [None] * settings.BACKUP_CODES_COUNT
    for idx, token in enumerate(tokens):
        token_list[idx] = token

    return token_list


def _recreate_backup_codes(user, num_codes=settings.BACKUP_CODES_COUNT):
    """Creates 10 new backup codes for a user, deletes all previous backup codes."""
    devices = get_user_static_device(user)
    if devices:
        devices.token_set.all().delete()
    else:
        devices = StaticDevice.objects.create(user=user, name="Static_Security_Codes")
    for n in range(num_codes):
        security_code = StaticToken.random_token()
        devices.token_set.create(token=security_code)

    _remove_low_on_codes_notification(user)


def _remove_low_on_codes_notification(user):
    """Remove the existing low on code notification if it exists"""
    existing_announcements = Announcement.objects.filter(
        Q(for_user=user) & Q(content_en__contains="To get more codes, visit")
    )
    if existing_announcements.count() > 0:
        for announcement in existing_announcements:
            announcement.delete()


######################
# Functions used by the Profiles module for 2fa login.
######################


def get_user_static_device(user, confirmed=None):
    devices = devices_for_user(user, confirmed=confirmed)
    for device in devices:
        if isinstance(device, StaticDevice):
            return device
