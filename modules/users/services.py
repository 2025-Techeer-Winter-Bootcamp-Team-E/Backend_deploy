from django.db import transaction
from .models import UserModel
from rest_framework_simplejwt.tokens import RefreshToken
class UserSignupService:
    """
    회원가입 로직
    """

    @staticmethod
    @transaction.atomic
    def create_user(data: dict) -> UserModel:
     
        email = data['email']
        password = data['password']
        nickname = data['nickname'] 
        name = data['name']
        phone = data['phone']


        user = UserModel.objects.create_user(
            email=email,
            password=password,
            nickname=nickname,
            name=name,
            phone=phone
        )

        return user 
    
class UserLoginService: #로그인 토큰 생성
    def get_login_token(self, user):
        token = RefreshToken.for_user(user) 
        return {
            'refresh': str(token),
            'access': str(token.access_token),
        }