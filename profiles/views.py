from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import PasswordChangeView, PasswordResetView
from django.utils.translation import gettext as _
from django.utils.translation import get_language
from django.utils.functional import cached_property
from django.views.generic import (
    CreateView,
    FormView,
    ListView,
    DeleteView,
    TemplateView,
    DetailView,
)
from django.views.generic.edit import UpdateView
from easyaudit.models import CRUDEvent
from django.contrib import messages
from django.urls import reverse_lazy
from django_otp import DEVICE_ID_SESSION_KEY, devices_for_user
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.expressions import RawSQL

from otp_yubikey.models import RemoteYubikeyDevice

from outbreaks.views import get_datetime_format
from portal.mixins import (
    ThrottledMixin,
    Is2FAMixin,
    IsAdminMixin,
    ProvinceAdminMixin,
    GetUserAdminMixin,
)
from backup_codes.views import get_user_static_device
from invitations.models import Invitation
from axes.models import AccessAttempt

from .utils import generate_2fa_code
from .utils.invitation_adapter import user_signed_up
from .models import HealthcareUser, HealthcareFailedAccessAttempt
from .mixins import (
    EditPasswordMixin,
    ProvinceAdminEditMixin,
    ProvinceAdminDeleteMixin,
)
from .forms import (
    SignupForm,
    SignupForm2fa,
    Healthcare2FAForm,
    HealthcareInviteForm,
    HealthcarePasswordResetForm,
    Resend2FACodeForm,
    YubikeyDeviceCreateForm,
    YubikeyVerifyForm,
)

from django.utils import translation


class YubikeyVerifyView(FormView):
    form_class = YubikeyVerifyForm
    template_name = "profiles/yubikey_verify.html"
    success_url = reverse_lazy("start")

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse_lazy("login"))

        if request.user.is_verified():
            return redirect(reverse_lazy("start"))

        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        device = self.request.user.remoteyubikeydevice_set.first()
        # Pass the device to the form
        kwargs.update({"device": device})
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)

        device = RemoteYubikeyDevice.objects.filter(user=self.request.user).first()
        self.request.user.otp_device = device
        self.request.session[DEVICE_ID_SESSION_KEY] = device.persistent_id

        return response


class YubikeyCreateView(CreateView):
    form_class = YubikeyDeviceCreateForm
    template_name = "profiles/yubikey_create.html"

    def _check_yubikey_exists_for_user(self, user):
        return True if RemoteYubikeyDevice.objects.filter(user=user).first() else False

    def get(self, request, *args, **kwargs):
        # Enforce 1 yubikey per user
        if self._check_yubikey_exists_for_user(self.request.user):
            return redirect(self.get_success_url())

        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("user_profile", kwargs={"pk": self.request.user.id})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add the currently logged user to the form
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        return response


class YubikeyDeleteView(Is2FAMixin, DeleteView):
    model = RemoteYubikeyDevice
    template_name = "profiles/yubikey_delete.html"

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        # If the user logged in with his yubikey in this session, he wont be verified anymore
        # So we need to send him a new SMS
        if request.user.is_verified() is False or isinstance(
            request.user.otp_device, RemoteYubikeyDevice
        ):
            generate_2fa_code(self.request.user)
        return response

    def get_success_url(self):
        return reverse_lazy("user_profile", kwargs={"pk": self.request.user.id})


class SignUpView(FormView):
    form_class = SignupForm
    template_name = "profiles/signup.html"

    def get_success_url(self):
        return reverse_lazy("signup_2fa")

    def get(self, request, *args, **kwargs):
        invited_email = self.request.session.get("account_verified_email", None)

        # if session variable or invitation is missing, redirect to "expired" page
        if not invited_email or not Invitation.objects.filter(
            email__iexact=invited_email
        ):
            return redirect("invite_expired")

        return super().get(request, *args, **kwargs)

    def get_initial(self):
        # preload the signup form with the email and the province of the admin
        invited_email = self.request.session.get("account_verified_email", None)
        inviter = self.get_inviter()
        return {
            "email": invited_email,
            "province": inviter.province.abbr,
        }

    def form_valid(self, form):
        form.save()
        user = authenticate(
            request=self.request,
            username=form.cleaned_data.get("email"),
            password=form.cleaned_data.get("password1"),
        )
        user_signed_up.send(sender=user.__class__, request=self.request, user=user)

        # Trigger sending a confirmation email
        inviter = self.get_inviter()
        form.send_mail(self.request.LANGUAGE_CODE, inviter.email)

        login(self.request, user)

        # delete matching access attempts for this user
        AccessAttempt.objects.filter(username=user.email).delete(),
        HealthcareFailedAccessAttempt.objects.filter(username=user.email).delete()

        return super(SignUpView, self).form_valid(form)

    def get_inviter(self):
        # get invite object and the admin user who sent the invite
        invited_email = self.request.session.get("account_verified_email", None)
        invitation = Invitation.objects.get(email__iexact=invited_email)
        admin = HealthcareUser.objects.get(id=invitation.inviter_id)
        return admin


class SignUp2FAView(LoginRequiredMixin, FormView):
    form_class = SignupForm2fa
    template_name = "profiles/signup_2fa.html"
    success_url = reverse_lazy("login_2fa")

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        existing_user = HealthcareUser.objects.get(pk=self.request.user.id)
        existing_user.phone_number = form.instance.phone_number
        existing_user.save()

        generate_2fa_code(self.request.user)

        return super(SignUp2FAView, self).form_valid(form)


class Login2FAView(LoginRequiredMixin, FormView):
    form_class = Healthcare2FAForm
    template_name = "profiles/2fa.html"
    success_url = reverse_lazy("start")

    @cached_property
    def has_mobile(self):
        return True if self.request.user.notifysmsdevice_set.exists() else False

    @cached_property
    def has_static_code(self):
        return True if self.request.user.staticdevice_set.exists() else False

    def get(self, request, *args, **kwargs):
        if request.user.is_verified():
            return redirect(reverse_lazy("start"))

        if request.user.remoteyubikeydevice_set.first() is not None:
            return redirect(reverse_lazy("yubikey_verify"))

        if not self.has_mobile and not self.has_static_code:
            return redirect(reverse_lazy("signup_2fa"))

        return super().get(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if settings.DEBUG:
            if self.has_mobile:
                sms_device = self.request.user.notifysmsdevice_set.last()
                initial["code"] = sms_device.token
            elif self.has_static_code:
                static_device = self.request.user.staticdevice_set.first()
                if static_device.token_set.count() > 0:
                    initial["code"] = static_device.token_set.first().token
        return initial

    def form_valid(self, form):
        code = form.cleaned_data.get("code")
        code_verfied = False
        sms_being_throttled = False
        backup_being_throttled = False
        locked_out = False

        if self.has_mobile:
            code_verfied, sms_being_throttled, locked_out = _verify_user_code(
                self.request, code, self.request.user.notifysmsdevice_set.all()
            )

        if not locked_out and not code_verfied and self.has_static_code:
            code_verfied, backup_being_throttled, locked_out = _verify_user_code(
                self.request, code, self.request.user.staticdevice_set.all()
            )

        if locked_out:
            return redirect(reverse_lazy("login"))

        if not code_verfied:
            # Just in case one of the device is throttled but another one
            # was verified
            if sms_being_throttled or backup_being_throttled:
                form.add_error("code", _("Please try again later."))

            else:
                form.add_error(
                    "code",
                    _("Something went wrong. Try again or ask for another code."),
                )

        if form.has_error("code"):
            return super().form_invalid(form)

        return super().form_valid(form)


class Resend2FAView(LoginRequiredMixin, FormView):
    form_class = Resend2FACodeForm
    template_name = "profiles/2fa-resend.html"
    success_url = reverse_lazy("login_2fa")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        is_valid = super().form_valid(form)
        if is_valid:
            messages.success(self.request, _("Log in code has been sent."))

        return is_valid


class InvitationView(Is2FAMixin, IsAdminMixin, ThrottledMixin, FormView):
    form_class = HealthcareInviteForm
    template_name = "invitations/templates/invite.html"
    success_url = reverse_lazy("invite_complete")
    throttled_model = Invitation
    throttled_limit = settings.MAX_INVITATIONS_PER_PERIOD
    throttled_time_range = settings.MAX_INVITATIONS_PERIOD_SECONDS
    throttled_lookup_user_field = "inviter"
    throttled_lookup_date_field = "created"

    def form_valid(self, form):
        # Pass user to invite, save the invite to the DB, and return it
        invite = form.save(user=self.request.user)
        if not settings.TESTING:
            # Don't actually send the email during tests
            invite.send_invitation(
                self.request,
                scheme=self.request.scheme,
                language=get_language(),
            )
        self.request.session["invite_email"] = invite.email
        return super().form_valid(form)

    def limit_reached(self):
        return render(self.request, "invitations/templates/locked.html", status=403)


class InvitationListView(Is2FAMixin, IsAdminMixin, ListView):
    template_name = "invitations/templates/invite_list.html"

    def get_queryset(self):
        return Invitation.objects.filter(
            inviter__province=self.request.user.province, accepted=False
        ).order_by("-sent")


class InvitationDeleteView(Is2FAMixin, IsAdminMixin, DeleteView):
    model = Invitation
    context_object_name = "invitation"
    success_url = reverse_lazy("invitation_list")
    template_name = "invitations/templates/invitation_confirm_delete.html"


class InvitationCompleteView(Is2FAMixin, IsAdminMixin, TemplateView):
    template_name = "invitations/templates/invite_complete.html"


class ProfilesView(Is2FAMixin, IsAdminMixin, ListView):
    def get_queryset(self):
        queryset = HealthcareUser.objects.filter(province=self.request.user.province)

        # don't return superusers when an admin user makes the request
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_superuser=False)

        # sorting rules: (a) current user on top, (b) then admins, (c) then staff by email address alphabetically
        return queryset.annotate(
            current_user_email=RawSQL("email = %s", (self.request.user.email,))
        ).order_by("-current_user_email", "-is_admin", "email")


class SupportView(GetUserAdminMixin, TemplateView):
    template_name = "profiles/templates/support.html"


class UserProfileView(Is2FAMixin, ProvinceAdminMixin, DetailView):
    model = HealthcareUser

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        healthcareuser = context["healthcareuser"]

        if healthcareuser.is_superuser:
            context["yubikey"] = RemoteYubikeyDevice.objects.filter(
                user=healthcareuser
            ).first()

        # True if this is an admin account viewing another admin account
        context["view_only"] = (
            healthcareuser.id != self.request.user.id
            and (not self.request.user.is_superuser)
            and healthcareuser.is_admin
        )

        # Get the number of log in Codes that currently exist
        _devices = get_user_static_device(healthcareuser)
        context["backup_codes_set"] = True if _devices else False
        context["backup_codes_count"] = (
            _devices.token_set.all().count() if _devices else 0
        )

        try:
            recent_date = (
                CRUDEvent.objects.filter(user_id=self.request.user.id)
                .filter(changed_fields__icontains="password")
                .first()
                .datetime
            )
            recent_date = self.request.convert_to_local_tz_from_utc(recent_date)
            context["last_updated_datetime"] = recent_date.strftime(
                get_datetime_format(translation.get_language())
            )
        except AttributeError:
            context["last_updated_datetime"] = ""

        return context


class HealthcareUserEditView(Is2FAMixin, ProvinceAdminEditMixin, UpdateView):
    model = HealthcareUser
    success_url = reverse_lazy("user_profile")

    def get_initial(self):
        initial = super().get_initial()
        user = self.get_object()
        initial["name"] = user.name
        return initial

    def get_success_url(self):
        return reverse_lazy("user_profile", kwargs={"pk": self.kwargs.get("pk")})


class HealthcarePasswordResetView(PasswordResetView):
    form_class = HealthcarePasswordResetForm

    def post(self, *args, **kwargs):
        base_url = self.request.build_absolute_uri("/")
        self.extra_email_context = {
            "base_url": base_url[:-1],  # remove the trailing slash
            "language": get_language(),
        }

        return super().post(*args, **kwargs)


class HealthcarePasswordChangeView(Is2FAMixin, EditPasswordMixin, PasswordChangeView):
    def get_success_url(self):
        return reverse_lazy("user_profile", kwargs={"pk": self.kwargs.get("pk")})


class UserDeleteView(Is2FAMixin, ProvinceAdminDeleteMixin, DeleteView):
    model = HealthcareUser
    context_object_name = "profile_user"
    success_url = reverse_lazy("profiles")

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.add_message(
            request,
            messages.SUCCESS,
            _("You deleted the account for ‘%(email)s’.")
            % {"email": self.object.email},
        )
        # This wont crash if no object is returned from the filtered query
        Invitation.objects.filter(email=self.object.email).delete()
        return response


def redirect_after_timed_out(request):
    messages.add_message(
        request,
        messages.INFO,
        _("Your session timed out. Log in again to continue using the portal."),
        "logout",
    )
    return redirect(reverse_lazy("login"))


def password_reset_complete(request):
    if request.user.remoteyubikeydevice_set.first() is not None:
        return redirect(reverse_lazy("yubikey_verify"))
    else:
        generate_2fa_code(request.user)
        return redirect(reverse_lazy("login_2fa"))


def _reset_all_devices_failure_count(user):
    devices = devices_for_user(user, None)
    for device in devices:
        device.throttling_failure_count = 0
        device.save()


def _verify_user_code(request, code, devices):
    being_throttled = False
    code_sucessful = False
    locked_out = False

    for device in devices:
        if device.throttling_failure_count >= settings.BACKUP_CODES_LOCKOUT_LIMIT - 1:
            # Lock the user out by setting them inactive
            request.user.is_active = False
            request.user.save()
            locked_out = True
            being_throttled = True
            _reset_all_devices_failure_count(request.user)
            break

        # let's check if the user is being throttled on the sms codes
        verified_allowed, errors_details = device.verify_is_allowed()
        if verified_allowed is False:
            being_throttled = True

        # Even though we know the device is being throttled, we still need to test it
        # If not, the throttling will never get increased for this device
        if device.verify_token(code):
            code_sucessful = True
            request.user.otp_device = device
            request.session[DEVICE_ID_SESSION_KEY] = device.persistent_id
            _reset_all_devices_failure_count(request.user)

    return [code_sucessful, being_throttled, locked_out]
