from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.authtoken.views import ObtainAuthToken


from exams.serializers import UserSerializer

User = get_user_model()

@extend_schema(
    tags=["Authentication"],
    summary="Register a new user",
    description=(
        "Creates a new user account and returns an authentication token. "
        "Users can register as students or instructors."
    ),
    request=UserSerializer,
    responses={
        201: UserSerializer,
        400: {"type": "object", "example": {"error": "Username already exists"}}
    }
)
class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint.
    Creates a new user and returns an authentication token.
    """
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Register new user and return token."""
        # Validate input data
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        role = request.data.get('role', User.Role.STUDENT)
        
        # Validation
        if not username or not email or not password:
            return Response(
                {'error': 'Username, email, and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Username already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'Email already registered'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            first_name=request.data.get('first_name', ''),
            last_name=request.data.get('last_name', ''),
            student_id=request.data.get('student_id')
        )
        
        # Generate token
        token, _ = Token.objects.get_or_create(user=user)
        
        # Serialize user data
        serializer = self.get_serializer(user)
        
        return Response(
            {
                'message': 'User registered successfully',
                'token': token.key,
                'user': serializer.data
            },
            status=status.HTTP_201_CREATED
        )
        
@extend_schema(
    tags=["Authentication"],
    summary="User login",
    description="Authenticate user and return an auth token."
)
class LoginView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response is None or not response.data:
            return Response(
                {'error': 'Authentication failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response({
            "token": response.data["token"]
        })

@extend_schema(
    tags=["Authentication"],
    summary="Logout user",
    description="Logs out the authenticated user by deleting their authentication token.",
    responses={
        200: {"type": "object", "example": {"message": "Successfully logged out"}},
        401: {"type": "object", "example": {"detail": "Authentication credentials were not provided."}},
    }
)
class LogoutView(APIView):
    """
    Logout endpoint.
    Deletes the user's authentication token.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Delete user's token."""
        try:
            request.user.auth_token.delete()
            return Response(
                {'message': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

@extend_schema(
    tags=["Users"],
    summary="Retrieve or update user profile",
    description=(
        "Allows an authenticated user to retrieve or update their own profile information."
    ),
)
@extend_schema_view(
    get=extend_schema(summary="Retrieve user profile"),
    put=extend_schema(summary="Update user profile"),
    patch=extend_schema(summary="Partially update user profile"),
)
class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    User profile endpoint.
    Allows users to view and update their profile.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Return the current user."""
        return self.request.user