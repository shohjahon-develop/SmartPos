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
            'role',         # O'qish uchun (RoleSerializer orqali)
            'role_id',      # <<<--- SHUNI QO'SHING (Yozish uchun)
            'salary',
            'address',
            'salary_status'
        ]
        # read_only_fields ga 'role' kiradi, 'role_id' emas (chunki u write_only)
        # write_only_fields ga 'role_id' kiradi
        extra_kwargs = {
            'role_id': {'write_only': True} # Bu yerda ham ko'rsatish mumkin
        }


class UserSerializer(serializers.ModelSerializer):
    # User ma'lumotlarini ko'rsatganda profilni ham qo'shib ko'rsatish
    profile = UserProfileSerializer(read_only=True) # Profilni o'zgartirish alohida bo'ladi

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile', 'is_active', 'date_joined']
        # ---- Tekshiring ----
        read_only_fields = ('date_joined', 'profile') # KORTEJ YOKI LIST

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})


    # Profil uchun maydonlar
    full_name = serializers.CharField(write_only=True, required=True, max_length=255, label="To'liq ismi")
    phone_number = serializers.CharField(write_only=True, required=False, max_length=20, allow_blank=True, label="Telefon raqami") # Ixtiyoriy qildik
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.exclude(name='Administrator'), # Admin rolini tanlab bo'lmaydi
        write_only=True,
        required=True, # Registratsiyada rol tanlanishi shart
        allow_null=False,
        label="Roli"
    )
    email = serializers.EmailField(required=True) # Emailni majburiy qildik
    salary = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True, write_only=True)
    address = serializers.CharField(required=False, allow_blank=True, write_only=True)


    class Meta:
        model = User
        fields = ('username', 'email', 'password',
                  'full_name', 'phone_number', 'role_id',
                  'salary', 'address')

    def validate(self, attrs):

        # Telefon raqam unikalligi (agar kiritilgan bo'lsa)
        phone = attrs.get('phone_number')
        if phone and UserProfile.objects.filter(phone_number=phone).exists():
             raise serializers.ValidationError({"phone_number": "Bu telefon raqami allaqachon mavjud."})

        # Username va email unikalligini Django o'zi tekshiradi (model darajasida)

        return attrs

    def create(self, validated_data):
        # Foydalanuvchini va profilini bir tranzaksiyada yaratish
        try:
            with transaction.atomic():
                # User modelidan kerakmas maydonlarni ajratib olish
                role = validated_data.pop('role_id')
                full_name = validated_data.pop('full_name')
                phone_number = validated_data.pop('phone_number', None)
                salary = validated_data.pop('salary', None)
                address = validated_data.pop('address', None)


                # User yaratish
                user = User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    password=validated_data['password']
                    # first_name va last_name ni ham full_name dan ajratib olish mumkin
                )

                profile = user.profile
                profile.full_name = full_name
                profile.phone_number = phone_number
                profile.role = role
                profile.salary = salary  # Yangi maydonlar
                profile.address = address  # Yangi maydonlar
                profile.save()

        except Exception as e:
             # Xatolik yuz bersa (masalan, username yoki email band bo'lsa)
             raise serializers.ValidationError(f"Registratsiya xatosi: {e}") # Yoki aniqroq xato

        return user


# --- Admin Tomonidan User Yaratish Uchun Yangi Serializer ---
class AdminUserCreateSerializer(serializers.ModelSerializer):
    # RegisterSerializer dagi kabi maydonlar + is_staff
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
    full_name = serializers.CharField(write_only=True, required=True, max_length=255, label="To'liq ismi")
    phone_number = serializers.CharField(write_only=True, required=False, max_length=20, allow_blank=True, label="Telefon raqami")
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), write_only=True, required=True, allow_null=False, label="Roli") # Hamma rollarni tanlay olishi mumkin
    email = serializers.EmailField(required=True)
    salary = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True, write_only=True)
    address = serializers.CharField(required=False, allow_blank=True, write_only=True)
    is_staff = serializers.BooleanField(required=False, default=False, write_only=True, label="Admin huquqi berilsinmi?") # Qo'shildi

    class Meta:
        model = User
        fields = ('username', 'email', 'password',
                  'full_name', 'phone_number', 'role_id',
                  'salary', 'address', 'is_staff') # is_staff qo'shildi

    def validate_email(self, value): # Email unikalligini tekshirish
        if User.objects.filter(email=value).exists(): raise serializers.ValidationError("Bu email allaqachon mavjud.")
        return value

    def validate_phone_number(self, value): # Telefon unikalligini tekshirish
        if value and UserProfile.objects.filter(phone_number=value).exists(): raise serializers.ValidationError("Bu telefon raqami allaqachon mavjud.")
        return value

    def create(self, validated_data):
        # RegisterSerializer.create dagi kabi, lekin is_staff ni ham hisobga oladi
        try:
            with transaction.atomic():
                role = validated_data.pop('role_id')
                full_name = validated_data.pop('full_name')
                phone_number = validated_data.pop('phone_number', None)
                salary = validated_data.pop('salary', None)
                address = validated_data.pop('address', None)
                make_staff = validated_data.pop('is_staff', False) # is_staff ni olamiz

                user = User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    password=validated_data['password'],
                    is_staff=make_staff # User yaratishda is_staff ni beramiz
                )

                # UserProfile ni yaratish/yangilash
                profile = user.profile # Signal endi yo'q deb hisoblaymiz (agar o'chirgan bo'lsangiz)
                                       # Agar signal qolgan bo'lsa, get_or_create ishlatish kerak
                # UserProfile.objects.get_or_create(user=user) # Agar signal yo'q bo'lsa
                profile.full_name = full_name
                profile.phone_number = phone_number
                profile.role = role
                profile.salary = salary
                profile.address = address
                profile.save()
        except Exception as e: raise serializers.ValidationError(f"Foydalanuvchi yaratish xatosi: {e}")
        return user

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        # Token payloadini o'zgartirish kerak bo'lsa, shu yerda qilinadi
        token = super().get_token(user)
        # Masalan: token['full_name'] = user.profile.full_name
        return token

    def validate(self, attrs):
        # 1. Ota klassning validatsiyasini chaqiramiz.
        # Bu login/parolni tekshiradi, self.user ni o'rnatadi
        # va {'refresh': '...', 'access': '...'} lug'atini qaytaradi (yoki AuthenticationFailed xatoligini beradi)
        try:
            data = super().validate(attrs)
        except Exception as e:
            # Agar ota klass validatsiyasida xatolik bo'lsa (masalan, AuthenticationFailed),
            # o'sha xatolikni qayta ko'taramiz.
            raise e

        # 2. Agar validatsiya muvaffaqiyatli bo'lsa, self.user mavjud bo'ladi.
        user = self.user
        user_role = None
        user_full_name = user.get_full_name() # Standart ism

        # 3. Profil ma'lumotlarini olishga harakat qilamiz (xatolik bo'lishi mumkin)
        try:
            if hasattr(user, 'profile'):
                profile = user.profile
                user_full_name = profile.full_name if profile.full_name else user_full_name
                if profile.role:
                    user_role = profile.role.name
        except Exception as e:
            # Profilni olishda xato bo'lsa, logga yozamiz, lekin ishni davom ettiramiz
            print(f"WARNING: Error fetching profile details for user {user.username} during login validate: {e}")

        # 4. Javobga qo'shimcha 'user' ma'lumotlarini qo'shamiz
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'full_name': user_full_name,
            'role': user_role,
            'is_superuser': user.is_superuser,
        }

        # 5. MUHIM: Yakuniy 'data' lug'atini qaytarish
        return data



class UserUpdateSerializer(serializers.ModelSerializer):
    # Profil maydonlarini alohida serializer orqali yoki to'g'ridan-to'g'ri olish
    profile = UserProfileSerializer(required=False) # Nested update uchun
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source='profile.role', write_only=True, required=False, allow_null=True
    )
    # User modelidagi o'zgartirish mumkin bo'lgan maydonlar
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    is_active = serializers.BooleanField(required=False)
    # Parolni alohida endpoint orqali o'zgartirish yaxshiroq

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'profile', 'role_id']
        # ---- Tekshiring ----
        read_only_fields = ('id',)

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        # Agar role_id kelgan bo'lsa, uni profile_data ga qo'shish shart emas,
        # chunki source='profile.role' orqali bog'langan

        # User ma'lumotlarini yangilash
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        # first_name, last_name ni ham profile.full_name dan ajratib olish mumkin
        instance.save()

        # Profil ma'lumotlarini yangilash
        profile = instance.profile
        # role_id allaqachon profile.role ga bog'langan (agar serializerda to'g'ri source berilgan bo'lsa)
        profile.full_name = profile_data.get('full_name', profile.full_name)
        profile.phone_number = profile_data.get('phone_number', profile.phone_number)
        profile.salary = profile_data.get('salary', profile.salary)
        profile.address = profile_data.get('address', profile.address)
        profile.salary_status = profile_data.get('salary_status', profile.salary_status)
        # role ni role_id orqali yangilash (agar role_id kelgan bo'lsa)
        # profile.role = validated_data.get('role_id', profile.role) # Bu kerak emas, source orqali bo'ladi
        profile.save()

        return instance

