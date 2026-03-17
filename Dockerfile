# Bước 1: Chọn base image
FROM nginx:alpine

# Bước 2: Chép file index.html vào thư mục mặc định của Nginx
# Thư mục web mặc định của Nginx là /usr/share/nginx/html
COPY index.html /usr/share/nginx/html/index.html

# Bước 3: Thông báo cổng mà container sẽ lắng nghe
EXPOSE 80