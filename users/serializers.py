# users/serializers.py
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Role, UserProfile


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']


class UserProfileSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source='role', write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = UserProfile
        fields = [
            'id',
            'full_name',
            'phone_number',
            'role',  # O'qish uchun (RoleSerializer orqali)
            'role_id',  # Yozish uchun
            'salary',
            'address',  # Mavjud edi
            'salary_payment_date',  # YANGI QO'SHILDI
            'salary_status'
        ]
        extra_kwargs = {
            'role_id': {'write_only': True}
        }


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile', 'is_active', 'date_joined']
        read_only_fields = ('date_joined', 'profile')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password],
                                     style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'},
                                      label="Parolni tasdiqlang")
    full_name = serializers.CharField(write_only=True, required=True, max_length=255, label="To'liq ismi")
    phone_number = serializers.CharField(write_only=True, required=False, max_length=20, allow_blank=True,
                                         label="Telefon raqami")
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.exclude(name='Administrator'), write_only=True,
                                                 required=True, allow_null=False, label="Roli")
    email = serializers.EmailField(required=True)
    salary = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True, write_only=True)
    address = serializers.CharField(required=False, allow_blank=True, write_only=True)  # Mavjud edi
    salary_payment_date = serializers.DateField(required=False, allow_null=True, write_only=True,
                                                label="Oylik to'lanadigan sana")  # YANGI QO'SHILDI

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2',
                  'full_name', 'phone_number', 'role_id',
                  'salary', 'address', 'salary_payment_date')  # YANGI QO'SHILDI

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                role = validated_data.pop('role_id')
                full_name = validated_data.pop('full_name')
                phone_number = validated_data.pop('phone_number', None)
                salary = validated_data.pop('salary', None)
                address = validated_data.pop('address', None)
                salary_payment_date = validated_data.pop('salary_payment_date', None)  # YANGI QO'SHILDI
                validated_data.pop('password2')

                user = User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    password=validated_data['password']
                )

                # UserProfile avtomatik signal orqali yaratiladi. Bu yerda uni olib, ma'lumotlarni o'rnatamiz.
                profile = user.profile  # Signal yaratgan profilni olamiz
                profile.full_name = full_name
                profile.phone_number = phone_number
                profile.role = role
                profile.salary = salary
                profile.address = address
                profile.salary_payment_date = salary_payment_date  # YANGI QO'SHILDI
                profile.save()
        except Exception as e:
            raise serializers.ValidationError(f"Registratsiya xatosi: {e}")
        return user


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password],
                                     style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'},
                                      label="Parolni tasdiqlang")
    full_name = serializers.CharField(write_only=True, required=True, max_length=255, label="To'liq ismi")
    phone_number = serializers.CharField(write_only=True, required=False, max_length=20, allow_blank=True,
                                         label="Telefon raqami")
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), write_only=True, required=True,
                                                 allow_null=False, label="Roli")
    email = serializers.EmailField(required=True)
    salary = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True, write_only=True)
    address = serializers.CharField(required=False, allow_blank=True, write_only=True)  # Mavjud edi
    salary_payment_date = serializers.DateField(required=False, allow_null=True, write_only=True,
                                                label="Oylik to'lanadigan sana")  # YANGI QO'SHILDI
    is_staff = serializers.BooleanField(required=False, default=False, write_only=True,
                                        label="Admin huquqi berilsinmi?")

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2',
                  'full_name', 'phone_number', 'role_id',
                  'salary', 'address', 'salary_payment_date', 'is_staff')  # YANGI QO'SHILDI

    def validate_email(self, value):
        if User.objects.filter(email=value).exists(): raise serializers.ValidationError("Bu email allaqachon mavjud.")
        return value

    def validate_phone_number(self, value):
        # Yangi user yaratilayotganda, instance bo'lmaydi, shuning uchun instance.pk ni tekshirish shart emas.
        if value and UserProfile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Bu telefon raqami bilan profil allaqachon mavjud.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                role = validated_data.pop('role_id')
                full_name = validated_data.pop('full_name')
                phone_number = validated_data.pop('phone_number', None)
                salary = validated_data.pop('salary', None)
                address = validated_data.pop('address', None)
                salary_payment_date = validated_data.pop('salary_payment_date', None)  # YANGI QO'SHILDI
                make_staff = validated_data.pop('is_staff', False)
                validated_data.pop('password2')

                user = User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    password=validated_data['password'],
                    is_staff=make_staff
                )

                profile = user.profile  # Signal yaratgan profilni olamiz
                profile.full_name = full_name
                profile.phone_number = phone_number
                profile.role = role
                profile.salary = salary
                profile.address = address
                profile.salary_payment_date = salary_payment_date  # YANGI QO'SHILDI
                profile.save()
        except Exception as e:
            raise serializers.ValidationError(f"Foydalanuvchi yaratish xatosi: {e}")
        return user


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except Exception as e:
            raise e

        user = self.user
        user_role = None
        user_full_name = user.get_full_name()

        try:
            if hasattr(user, 'profile'):
                profile = user.profile
                user_full_name = profile.full_name if profile.full_name else user_full_name
                if profile.role:
                    user_role = profile.role.name
        except Exception as e:
            print(f"WARNING: Error fetching profile details for user {user.username} during login validate: {e}")

        data['user'] = {
            'id': user.id,
            'username': user.username,
            'full_name': user_full_name,
            'role': user_role,
            'is_superuser': user.is_superuser,
        }
        return data


class UserUpdateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=False)  # UserProfileSerializer da salary_payment_date bor
    # role_id ni profile ichida yuborish mumkin, lekin alohida qoldirsak ham bo'ladi
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source='profile.role', write_only=True, required=False, allow_null=True,
        label="Roli (ID)"
    )
    full_name = serializers.CharField(source='profile.full_name', required=False, label="To'liq ismi")
    phone_number = serializers.CharField(source='profile.phone_number', required=False, allow_null=True,
                                         label="Telefon raqami")
    salary = serializers.DecimalField(source='profile.salary', max_digits=15, decimal_places=2, required=False,
                                      allow_null=True, label="Oylik maosh")
    address = serializers.CharField(source='profile.address', required=False, allow_blank=True, allow_null=True,
                                    label="Manzil")
    salary_payment_date = serializers.DateField(source='profile.salary_payment_date', required=False, allow_null=True,
                                                label="Oylik to'lanadigan sana")  # YANGI QO'SHILDI
    salary_status = serializers.ChoiceField(source='profile.salary_status', choices=UserProfile.salary_status_choices,
                                            required=False, allow_blank=True, allow_null=True, label="Oylik holati")

    # User modelidagi o'zgartirish mumkin bo'lgan maydonlar
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False, label="Admin huquqi")

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'is_active', 'is_staff',  # User modelidan
            'full_name', 'phone_number', 'role_id',  # Profile dan (source orqali)
            'salary', 'address', 'salary_payment_date', 'salary_status',  # Profile dan (source orqali)
            'profile'  # O'qish uchun (agar profile nested ko'rsatilsa)
        ]
        read_only_fields = ('id', 'profile')  # profile o'qish uchun, yozish uchun alohida maydonlar

    def validate_phone_number(self, value):
        # Tahrirlashda joriy userning profilidagi telefon raqamini hisobga olmaslik kerak
        instance = self.instance  # Bu User instansi
        if value and UserProfile.objects.filter(phone_number=value).exclude(user=instance).exists():
            raise serializers.ValidationError("Bu telefon raqami bilan boshqa profil allaqachon mavjud.")
        return value

    def validate_email(self, value):
        instance = self.instance  # User instansi
        if value and User.objects.filter(email=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError("Bu email bilan boshqa foydalanuvchi allaqachon mavjud.")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})  # Agar 'profile' to'g'ridan-to'g'ri kelsa
        # Lekin biz source orqali ishlayapmiz

        # User ma'lumotlarini yangilash
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.is_staff = validated_data.get('is_staff', instance.is_staff)
        instance.save()

        # Profil ma'lumotlarini yangilash
        # UserProfile.objects.update_or_create metodi qulay bo'lishi mumkin,
        # lekin signal profilni yaratganligi uchun instance.profile mavjud bo'lishi kerak.
        profile, created = UserProfile.objects.get_or_create(user=instance)

        # role_id orqali kelgan rol source='profile.role' bilan avtomatik o'rnatiladi
        # Agar 'role_id' alohida validated_data da qolgan bo'lsa, uni olish kerak
        # role = validated_data.get('role_id', profile.role) # source ishlatilgani uchun bu shartmas
        # profile.role = role

        profile.full_name = validated_data.get('full_name', profile.full_name)
        profile.phone_number = validated_data.get('phone_number', profile.phone_number)
        profile.salary = validated_data.get('salary', profile.salary)
        profile.address = validated_data.get('address', profile.address)
        profile.salary_payment_date = validated_data.get('salary_payment_date',
                                                         profile.salary_payment_date)  # YANGI QO'SHILDI
        profile.salary_status = validated_data.get('salary_status', profile.salary_status)
        profile.save()

        return instance


# # users/serializers.py
# from django.contrib.auth.models import User
# from django.contrib.auth.password_validation import validate_password
# from django.db import transaction
# from rest_framework import serializers
# from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
#
# from .models import Role, UserProfile
#
#
# class RoleSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Role
#         fields = ['id', 'name', 'description']
#
#
#
# class UserProfileSerializer(serializers.ModelSerializer):
#     role = RoleSerializer(read_only=True)
#     role_id = serializers.PrimaryKeyRelatedField(
#         queryset=Role.objects.all(), source='role', write_only=True, required=False, allow_null=True
#     )
#
#     class Meta:
#         model = UserProfile
#         fields = [
#             'id',
#             'full_name',
#             'phone_number',
#             'role',         # O'qish uchun (RoleSerializer orqali)
#             'role_id',      # <<<--- SHUNI QO'SHING (Yozish uchun)
#             'salary',
#             'address',
#             'salary_status'
#         ]
#         # read_only_fields ga 'role' kiradi, 'role_id' emas (chunki u write_only)
#         # write_only_fields ga 'role_id' kiradi
#         extra_kwargs = {
#             'role_id': {'write_only': True} # Bu yerda ham ko'rsatish mumkin
#         }
#
#
# class UserSerializer(serializers.ModelSerializer):
#     # User ma'lumotlarini ko'rsatganda profilni ham qo'shib ko'rsatish
#     profile = UserProfileSerializer(read_only=True) # Profilni o'zgartirish alohida bo'ladi
#
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile', 'is_active', 'date_joined']
#         # ---- Tekshiring ----
#         read_only_fields = ('date_joined', 'profile') # KORTEJ YOKI LIST
#
# class RegisterSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
#     # --- QAYTA QO'SHILDI ---
#     password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'}, label="Parolni tasdiqlang")
#     # --------------------
#     full_name = serializers.CharField(write_only=True, required=True, max_length=255, label="To'liq ismi")
#     phone_number = serializers.CharField(write_only=True, required=False, max_length=20, allow_blank=True, label="Telefon raqami")
#     role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.exclude(name='Administrator'), write_only=True, required=True, allow_null=False, label="Roli")
#     email = serializers.EmailField(required=True)
#     salary = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True, write_only=True)
#     address = serializers.CharField(required=False, allow_blank=True, write_only=True)
#
#     class Meta:
#         model = User
#         # --- password2 QO'SHILDI ---
#         fields = ('username', 'email', 'password', 'password2',
#                   'full_name', 'phone_number', 'role_id',
#                   'salary', 'address')
#         # -----------------------
#
#     def validate(self, attrs):
#         # --- PAROLNI SOLISHTIRISH QAYTA QO'SHILDI ---
#         if attrs['password'] != attrs['password2']:
#             raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})
#         # ------------------------------------------
#         return attrs
#
#     def create(self, validated_data):
#         try:
#             with transaction.atomic():
#                 role = validated_data.pop('role_id')
#                 full_name = validated_data.pop('full_name')
#                 phone_number = validated_data.pop('phone_number', None)
#                 salary = validated_data.pop('salary', None)
#                 address = validated_data.pop('address', None)
#                 # --- password2 ni POP QILISH QO'SHILDI ---
#                 password2 = validated_data.pop('password2') # User.objects.create_user ga kerak emas
#                 # --------------------------------------
#
#                 user = User.objects.create_user(
#                     username=validated_data['username'],
#                     email=validated_data['email'],
#                     password=validated_data['password']
#                 )
#
#                 # UserProfile yaratish/yangilash
#                 profile, created = UserProfile.objects.get_or_create(user=user) # get_or_create xavfsizroq
#                 profile.full_name = full_name
#                 profile.phone_number = phone_number
#                 profile.role = role
#                 profile.salary = salary
#                 profile.address = address
#                 profile.save()
#         except Exception as e: raise serializers.ValidationError(f"Registratsiya xatosi: {e}")
#         return user
#
# # --- Admin Tomonidan User Yaratish Uchun Serializer (password2 qaytarildi) ---
# class AdminUserCreateSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
#     # --- QAYTA QO'SHILDI ---
#     password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'}, label="Parolni tasdiqlang")
#     # --------------------
#     full_name = serializers.CharField(write_only=True, required=True, max_length=255, label="To'liq ismi")
#     phone_number = serializers.CharField(write_only=True, required=False, max_length=20, allow_blank=True, label="Telefon raqami")
#     role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), write_only=True, required=True, allow_null=False, label="Roli")
#     email = serializers.EmailField(required=True)
#     salary = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True, write_only=True)
#     address = serializers.CharField(required=False, allow_blank=True, write_only=True)
#     is_staff = serializers.BooleanField(required=False, default=False, write_only=True, label="Admin huquqi berilsinmi?")
#
#     class Meta:
#         model = User
#         # --- password2 QO'SHILDI ---
#         fields = ('username', 'email', 'password', 'password2',
#                   'full_name', 'phone_number', 'role_id',
#                   'salary', 'address', 'is_staff')
#         # -----------------------
#
#     def validate_email(self, value):
#         if User.objects.filter(email=value).exists(): raise serializers.ValidationError("Bu email allaqachon mavjud.")
#         return value
#
#     def validate_phone_number(self, value):
#         if value and UserProfile.objects.filter(phone_number=value).exists(): raise serializers.ValidationError("Bu telefon raqami allaqachon mavjud.")
#         return value
#
#     # --- PAROLNI SOLISHTIRISH QAYTA QO'SHILDI ---
#     def validate(self, attrs):
#         if attrs['password'] != attrs['password2']:
#             raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})
#         return attrs
#     # ------------------------------------------
#
#     def create(self, validated_data):
#         try:
#             with transaction.atomic():
#                 role = validated_data.pop('role_id')
#                 full_name = validated_data.pop('full_name')
#                 phone_number = validated_data.pop('phone_number', None)
#                 salary = validated_data.pop('salary', None)
#                 address = validated_data.pop('address', None)
#                 make_staff = validated_data.pop('is_staff', False)
#                 # --- password2 ni POP QILISH QO'SHILDI ---
#                 password2 = validated_data.pop('password2')
#                 # --------------------------------------
#
#                 user = User.objects.create_user(
#                     username=validated_data['username'],
#                     email=validated_data['email'],
#                     password=validated_data['password'],
#                     is_staff=make_staff
#                 )
#
#                 profile, created = UserProfile.objects.get_or_create(user=user) # get_or_create
#                 profile.full_name = full_name
#                 profile.phone_number = phone_number
#                 profile.role = role
#                 profile.salary = salary
#                 profile.address = address
#                 profile.save()
#         except Exception as e: raise serializers.ValidationError(f"Foydalanuvchi yaratish xatosi: {e}")
#         return user
#
# class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
#     @classmethod
#     def get_token(cls, user):
#         # Token payloadini o'zgartirish kerak bo'lsa, shu yerda qilinadi
#         token = super().get_token(user)
#         # Masalan: token['full_name'] = user.profile.full_name
#         return token
#
#     def validate(self, attrs):
#         # 1. Ota klassning validatsiyasini chaqiramiz.
#         # Bu login/parolni tekshiradi, self.user ni o'rnatadi
#         # va {'refresh': '...', 'access': '...'} lug'atini qaytaradi (yoki AuthenticationFailed xatoligini beradi)
#         try:
#             data = super().validate(attrs)
#         except Exception as e:
#             # Agar ota klass validatsiyasida xatolik bo'lsa (masalan, AuthenticationFailed),
#             # o'sha xatolikni qayta ko'taramiz.
#             raise e
#
#         # 2. Agar validatsiya muvaffaqiyatli bo'lsa, self.user mavjud bo'ladi.
#         user = self.user
#         user_role = None
#         user_full_name = user.get_full_name() # Standart ism
#
#         # 3. Profil ma'lumotlarini olishga harakat qilamiz (xatolik bo'lishi mumkin)
#         try:
#             if hasattr(user, 'profile'):
#                 profile = user.profile
#                 user_full_name = profile.full_name if profile.full_name else user_full_name
#                 if profile.role:
#                     user_role = profile.role.name
#         except Exception as e:
#             # Profilni olishda xato bo'lsa, logga yozamiz, lekin ishni davom ettiramiz
#             print(f"WARNING: Error fetching profile details for user {user.username} during login validate: {e}")
#
#         # 4. Javobga qo'shimcha 'user' ma'lumotlarini qo'shamiz
#         data['user'] = {
#             'id': user.id,
#             'username': user.username,
#             'full_name': user_full_name,
#             'role': user_role,
#             'is_superuser': user.is_superuser,
#         }
#
#         # 5. MUHIM: Yakuniy 'data' lug'atini qaytarish
#         return data
#
#
#
# class UserUpdateSerializer(serializers.ModelSerializer):
#     # Profil maydonlarini alohida serializer orqali yoki to'g'ridan-to'g'ri olish
#     profile = UserProfileSerializer(required=False) # Nested update uchun
#     role_id = serializers.PrimaryKeyRelatedField(
#         queryset=Role.objects.all(), source='profile.role', write_only=True, required=False, allow_null=True
#     )
#     # User modelidagi o'zgartirish mumkin bo'lgan maydonlar
#     username = serializers.CharField(required=False)
#     email = serializers.EmailField(required=False)
#     is_active = serializers.BooleanField(required=False)
#     # Parolni alohida endpoint orqali o'zgartirish yaxshiroq
#
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'profile', 'role_id']
#         # ---- Tekshiring ----
#         read_only_fields = ('id',)
#
#     def update(self, instance, validated_data):
#         profile_data = validated_data.pop('profile', {})
#         # Agar role_id kelgan bo'lsa, uni profile_data ga qo'shish shart emas,
#         # chunki source='profile.role' orqali bog'langan
#
#         # User ma'lumotlarini yangilash
#         instance.username = validated_data.get('username', instance.username)
#         instance.email = validated_data.get('email', instance.email)
#         instance.is_active = validated_data.get('is_active', instance.is_active)
#         # first_name, last_name ni ham profile.full_name dan ajratib olish mumkin
#         instance.save()
#
#         # Profil ma'lumotlarini yangilash
#         profile = instance.profile
#         # role_id allaqachon profile.role ga bog'langan (agar serializerda to'g'ri source berilgan bo'lsa)
#         profile.full_name = profile_data.get('full_name', profile.full_name)
#         profile.phone_number = profile_data.get('phone_number', profile.phone_number)
#         profile.salary = profile_data.get('salary', profile.salary)
#         profile.address = profile_data.get('address', profile.address)
#         profile.salary_status = profile_data.get('salary_status', profile.salary_status)
#         # role ni role_id orqali yangilash (agar role_id kelgan bo'lsa)
#         # profile.role = validated_data.get('role_id', profile.role) # Bu kerak emas, source orqali bo'ladi
#         profile.save()
#
#         return instance
#
