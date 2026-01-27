from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import UserModel

# 1. 회원가입 데이터를 담을 그릇(Serializer)의 이름을 정합니다.
class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    # 이메일 중복 체크 로직
    def validate_email(self, value):
        """이메일이 이미 존재하는지 확인합니다."""
        if UserModel.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 존재하는 이메일입니다.")
        return value
    
    class Meta: 
        model=UserModel 
        fields=['id', 'email', 'password','nickname','name','phone','created_at']
        extra_kwargs = {
            'password': {'write_only': True},
            'id': {'read_only': True},        # 출력만 하고 입력은 안 받음 (명세서 반영)
            'created_at': {'read_only': True},
        }

class UserLoginSerializer(serializers.Serializer):
    email=serializers.EmailField()
    password=serializers.CharField(style={'input_type':'password'})
    
    def validate(self, data):
        email=data['email']
        password=data['password']
        user=authenticate(username=email,password=password)
        if user is not None:
            data['user']=user
            return data
        else:
            raise serializers.ValidationError("이메일 또는 비밀번호가 일치하지 않습니다.")
        
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        # 명세서 Response Body의 data 안에 있는 필드들과 일치시킵니다.
        fields = ['name', 'email', 'nickname', 'phone']


            
