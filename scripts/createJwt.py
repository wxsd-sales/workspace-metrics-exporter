import jwt

def createJwt(refreshToken, appUrl, oauthUrl):
    basicToken = {
        'refreshToken': refreshToken,
        'oauthUrl': oauthUrl,
        'appUrl': appUrl
    }
    encoded_jwt = jwt.encode(basicToken, 'secret', algorithm='HS256')
    return encoded_jwt
