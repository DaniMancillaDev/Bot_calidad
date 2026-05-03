#!/data/data/com.termux/files/usr/bin/bash

echo "=========================================="
echo "   INSTALADOR PRO PARA ANDROID (UBUNTU)"
echo "=========================================="

# 1. Instalar proot-distro en Termux
echo "📦 Instalando gestor de distribuciones..."
pkg update && pkg upgrade -y
pkg install proot-distro -y

# 2. Instalar Ubuntu
echo "🌍 Instalando Ubuntu (esto puede tardar unos minutos)..."
proot-distro install ubuntu

# 3. Crear script de configuración interna para Ubuntu
cat << 'EOF' > setup_interno.sh
#!/bin/bash
echo "⚙️ Configurando entorno dentro de Ubuntu..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv libjpeg-dev libpng-dev libgomp1

# Crear entorno virtual y cargar dependencias
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install onnxruntime

echo "✅ Entorno Ubuntu configurado con éxito."
EOF

# 4. Mover el script interno y ejecutarlo dentro de Ubuntu
echo "🚀 Entrando a Ubuntu para finalizar la configuración..."
proot-distro login ubuntu --bind .:/root/bot_calidad -- bash -c "cd /root/bot_calidad && bash setup_interno.sh"

# 5. Crear el lanzador final
cat << 'EOF' > run_pro.sh
#!/data/data/com.termux/files/usr/bin/bash
echo "🔥 Lanzando Bot + Web desde Ubuntu (Con soporte IA)..."
proot-distro login ubuntu --bind .:/root/bot_calidad -- bash -c "cd /root/bot_calidad && source venv/bin/activate && python3 run_bot.py & cd web && python3 manage.py runserver"
EOF

chmod +x run_pro.sh

echo "=========================================="
echo "🎉 ¡LISTO! Todo configurado."
echo "Para iniciar el sistema usa: ./run_pro.sh"
echo "=========================================="
