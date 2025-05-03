# users/serializers.py
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from subscriptions.models import SubscriptionPlan
from .models import Role, UserProfile, Store


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']


class UserProfileSerializer(serializers.ModelSerializer):
    # Rolni faqat o'qish uchun ID va nomini ko'rsatish
    role = RoleSerializer(read_only=True)
    # Rolni yozish (yaratish/tahrirlash) uchun faqat ID ni qabul qilish
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source='role', write_only=True, required=False, allow_null=True
    )
    store_id = serializers.IntegerField(source='store.id', read_only=True, allow_null=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'store_id',  # Store ID qo'shildi
            'full_name', 'phone_number', 'role', 'role_id',
            # Yangi maydonlar (Xodimlar ro'yxati uchun)
            'salary', 'address', 'salary_status'
        ]


class UserSerializer(serializers.ModelSerializer):
    # User ma'lumotlarini ko'rsatganda profilni ham qo'shib ko'rsatish
    profile = UserProfileSerializer(read_only=True) # Profilni o'zgartirish alohida bo'ladi

    class Meta:
        model = User
        # 'password' ni bu yerda ko'rsatmaymiz!
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile', 'is_active', 'date_joined']
        read_only_fields = ['date_joined', 'profile']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'}, label="Parolni tasdiqlang")

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
        fields = ('username', 'email', 'password', 'password2',
                  'full_name', 'phone_number', 'role_id',
                  'salary', 'address')

    def validate(self, attrs):
        # Parol tasdiqlanishi
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})

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
                password2 = validated_data.pop('password2') # Kerak emas endi
                salary = validated_data.pop('salary', None)
                address = validated_data.pop('address', None)
                store = validated_data.pop('store', None)

                # User yaratish
                user = User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    password=validated_data['password']
                    # first_name va last_name ni ham full_name dan ajratib olish mumkin
                )

                profile = user.profile
                profile.store = store  # Store ni belgilash
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
        read_only_fields = ['id']

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

# --- Superadmin uchun Serializerlar ---

class SubscriptionPlanSimpleSerializer(serializers.ModelSerializer):
     """Obuna tarifini qisqacha ko'rsatish uchun"""
     class Meta:
         model = SubscriptionPlan
         fields = ['id', 'name', 'price_uzs']

class StoreOwnerSerializer(serializers.ModelSerializer):
    """Do'kon egasini ko'rsatish uchun"""
    full_name = serializers.CharField(source='profile.full_name', read_only=True)
    phone_number = serializers.CharField(source='profile.phone_number', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'phone_number']

class StoreListSerializer(serializers.ModelSerializer):
    """Do'konlar ro'yxati uchun (Superadmin)"""
    owner = StoreOwnerSerializer(read_only=True)
    subscription_plan = SubscriptionPlanSimpleSerializer(read_only=True)
    # Balki joriy xodimlar soni? mahsulot soni? (annotate qilish kerak)
    # users_count = serializers.IntegerField(read_only=True)
    # products_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'owner', 'subscription_plan',
            'expiry_date', 'is_active', 'created_at'
            # 'users_count', 'products_count'
        ]

class StoreDetailSerializer(StoreListSerializer):
     """Bitta do'konning batafsil ma'lumoti (Superadmin)"""
     # Batafsil obuna ma'lumoti
     subscription_plan = SubscriptionPlanSimpleSerializer(read_only=True) # Yoki to'liq SubscriptionPlanSerializer
     # Qo'shimcha ma'lumotlar (masalan, limitlar)
     class Meta(StoreListSerializer.Meta):
          fields = StoreListSerializer.Meta.fields # + qo'shimcha maydonlar

class StoreCreateSerializer(serializers.Serializer):
     """Yangi do'kon va egasini yaratish uchun (Superadmin)"""
     # Store fields
     store_name = serializers.CharField(max_length=255, label="Do'kon Nomi")
     subscription_plan_id = serializers.PrimaryKeyRelatedField(
         queryset=SubscriptionPlan.objects.filter(is_active=True),
         label="Obuna Tarifi"
     )
     expiry_date = serializers.DateField(required=False, allow_null=True, label="Amal qilish Muddati") # Odatda avtomatik hisoblanadi

     # Owner (User) fields
     owner_username = serializers.CharField(max_length=150, label="Eganing Foydalanuvchi Nomi")
     owner_email = serializers.EmailField(label="Eganing Email")
     owner_password = serializers.CharField(
         write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'}, label="Eganing Paroli"
     )
     owner_full_name = serializers.CharField(max_length=255, label="Eganing To'liq Ismi")
     owner_phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, label="Eganing Telefon Raqami")

     def validate_owner_username(self, value):
         if User.objects.filter(username=value).exists():
             raise serializers.ValidationError("Bu username allaqachon mavjud.")
         return value

     def validate_owner_email(self, value):
         if User.objects.filter(email=value).exists():
             raise serializers.ValidationError("Bu email allaqachon mavjud.")
         return value

     def validate_owner_phone_number(self, value):
         if value and UserProfile.objects.filter(phone_number=value).exists():
             raise serializers.ValidationError("Bu telefon raqami allaqachon mavjud.")
         return value

     @transaction.atomic
     def create(self, validated_data):
         # 1. Owner User yaratish
         owner = User.objects.create_user(
             username=validated_data['owner_username'],
             email=validated_data['owner_email'],
             password=validated_data['owner_password'],
             # is_staff=True # Do'kon egasi admin paneliga kira olsinmi?
         )

         # 2. Owner UserProfile yaratish (yoki yangilash - signal orqali)
         profile = owner.profile # Signal yaratgan bo'lishi kerak
         profile.full_name = validated_data['owner_full_name']
         profile.phone_number = validated_data.get('owner_phone_number')
         # Egasi uchun standart 'Admin' rolini belgilash
         try:
             admin_role = Role.objects.get(name='Admin') # Yoki boshqa nom
             profile.role = admin_role
         except Role.DoesNotExist:
             print("WARNING: 'Admin' role not found for store owner.")
             # Yoki xatolik qaytarish?
             pass
         # profile.save() # Store yaratilgandan keyin saqlaymiz

         # 3. Store yaratish
         store = Store.objects.create(
             name=validated_data['store_name'],
             owner=owner,
             subscription_plan=validated_data['subscription_plan_id'],
             expiry_date=validated_data.get('expiry_date'),
             is_active=True # Default aktiv
         )

         # 4. Profilni Store ga bog'lash va saqlash
         profile.store = store
         profile.save()

         # Natijani qaytarish (masalan, yaratilgan do'kon ma'lumoti)
         # StoreDetailSerializer dan foydalanish mumkin
         return StoreDetailSerializer(store, context=self.context).data

class StoreUpdateSerializer(serializers.ModelSerializer):
    """Do'konni yangilash uchun (Superadmin)"""
    # Faqat Superadmin o'zgartirishi mumkin bo'lgan maydonlar
    subscription_plan_id = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        source='subscription_plan', required=False, allow_null=True
    )
    owner_id = serializers.PrimaryKeyRelatedField(
         queryset=User.objects.filter(is_superuser=False), # Superuserni ega qilib bo'lmaydi
         source='owner', required=False
    )

    class Meta:
        model = Store
        fields = ['name', 'subscription_plan_id', 'expiry_date', 'is_active', 'owner_id']
