output "instance_id" {
  value = aws_instance.backend.id
}

output "public_ip" {
  value = aws_instance.backend.public_ip
}

output "public_dns" {
  value = aws_instance.backend.public_dns
}

output "api_url" {
  value = "http://${aws_instance.backend.public_ip}"
}
