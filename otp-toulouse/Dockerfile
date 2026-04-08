
FROM eclipse-temurin:21-jre-jammy
 
WORKDIR /otp
 
# Copie du jar OTP (depuis bin/)
COPY bin/*.jar otp.jar
 
# Données de routage (graph pré-construit + configs)
COPY toulouse/ /var/otp/toulouse/
 
EXPOSE 8080
 
# --load : charge le graph.obj existant sans rebuild
CMD ["java", "-Xmx4G", "-jar", "otp.jar", \
     "--load", "/var/otp/toulouse", \
     "--port", "8080"]
