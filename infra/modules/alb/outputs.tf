output "alb_arn" { value = aws_lb.this.arn }
output "alb_dns_name" { value = aws_lb.this.dns_name }
output "listener_http_arn" { value = aws_lb_listener.http.arn }
output "alb_sg_id" { value = aws_security_group.alb.id }
output "dns_name" { value = aws_lb.this.dns_name }
