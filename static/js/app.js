// ERP 시스템 JavaScript

// 전역 변수
let accessToken = localStorage.getItem('access_token');

// 로그아웃 함수
function logout() {
    if (confirm('로그아웃 하시겠습니까?')) {
        fetch('/logout', {
            method: 'POST',
            credentials: 'include'
        }).then(() => {
            window.location.href = '/';
        });
    }
}

// API 요청 헬퍼 함수
async function apiRequest(url, options = {}) {
    const token = localStorage.getItem('access_token');
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` })
        }
    };
    
    const finalOptions = { ...defaultOptions, ...options };
    
    try {
        const response = await fetch(url, finalOptions);
        
        if (response.status === 401) {
            // 토큰 만료 또는 인증 실패
            localStorage.removeItem('access_token');
            window.location.href = '/login';
            return null;
        }
        
        return response;
    } catch (error) {
        console.error('API 요청 실패:', error);
        throw error;
    }
}

// 알림 표시 함수
function showNotification(message, type = 'info') {
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    }[type] || 'alert-info';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // 5초 후 자동 제거
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
}

// 로딩 표시 함수
function showLoading(element) {
    element.innerHTML = '<div class="loading"></div>';
}

// 숫자 포맷팅 함수
function formatNumber(num) {
    return new Intl.NumberFormat('ko-KR').format(num);
}

// 날짜 포맷팅 함수
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 재고 상태 확인 함수
function getStockStatus(quantity) {
    if (quantity === 0) return { class: 'bg-danger', text: '품절' };
    if (quantity <= 5) return { class: 'bg-warning', text: '부족' };
    if (quantity <= 10) return { class: 'bg-info', text: '보통' };
    return { class: 'bg-success', text: '충분' };
}

// 폼 유효성 검사 함수
function validateForm(formElement) {
    const requiredFields = formElement.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// 재고 수량 실시간 업데이트
function updateStockQuantity(productId, change) {
    const stockElement = document.querySelector(`[data-product-id="${productId}"] .stock-quantity`);
    if (stockElement) {
        const currentStock = parseInt(stockElement.textContent);
        const newStock = currentStock + change;
        stockElement.textContent = newStock;
        
        // 재고 상태 업데이트
        const status = getStockStatus(newStock);
        const badgeElement = stockElement.parentElement.querySelector('.badge');
        if (badgeElement) {
            badgeElement.className = `badge ${status.class}`;
            badgeElement.textContent = status.text;
        }
    }
}

// 사용자 정보 확인 및 관리자 메뉴 표시
async function checkUserRole() {
    console.log('DEBUG: checkUserRole 함수 실행');
    try {
        const response = await fetch('/api/user/me', {
            credentials: 'include'
        });
        
        console.log('DEBUG: /api/user/me 응답 상태:', response.status);
        
        if (response.ok) {
            const user = await response.json();
            console.log('DEBUG: 사용자 정보:', user);
            const adminMenuItem = document.getElementById('admin-menu-item');
            
            if (user.is_admin && adminMenuItem) {
                adminMenuItem.style.display = 'block';
                console.log('DEBUG: 관리자 메뉴 표시됨');
            }
        } else {
            console.log('DEBUG: 사용자 정보 요청 실패, 상태:', response.status);
        }
    } catch (error) {
        console.log('사용자 정보 확인 실패:', error);
    }
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('DEBUG: DOMContentLoaded 실행됨, 현재 경로:', window.location.pathname);
    
    // 쿠키 기반 인증이므로 localStorage 토큰 체크 제거
    // 서버에서 쿠키를 통해 인증을 처리함
    
    // 관리자 메뉴 표시 확인
    if (!window.location.pathname.includes('/login') && 
        !window.location.pathname.includes('/register') && 
        window.location.pathname !== '/') {
        console.log('DEBUG: 관리자 메뉴 체크 실행');
        checkUserRole();
    }
    
    // 모든 폼에 유효성 검사 추가
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                showNotification('필수 항목을 모두 입력해주세요.', 'warning');
            }
        });
    });
    
    // 숫자 입력 필드에 포맷팅 추가
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value) {
                this.value = parseFloat(this.value).toFixed(2);
            }
        });
    });
});

// 전역 에러 핸들러
window.addEventListener('error', function(e) {
    console.error('전역 에러:', e.error);
    showNotification('예상치 못한 오류가 발생했습니다.', 'error');
});

// 네트워크 오류 핸들러
window.addEventListener('unhandledrejection', function(e) {
    console.error('Promise rejection:', e.reason);
    showNotification('네트워크 오류가 발생했습니다.', 'error');
});
