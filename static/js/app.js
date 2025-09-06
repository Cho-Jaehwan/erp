// 재고관리 시스템 JavaScript

// 전역 변수
let accessToken = localStorage.getItem('access_token');

// 토큰 자동 갱신 함수
async function refreshAccessToken() {
    try {
        const response = await fetch('/api/refresh-token', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            // 새로운 액세스 토큰을 쿠키에서 가져와서 localStorage에 저장
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'access_token') {
                    localStorage.setItem('access_token', value);
                    accessToken = value;
                    console.log('토큰이 자동으로 갱신되었습니다.');
                    return true;
                }
            }
        }
        return false;
    } catch (error) {
        console.error('토큰 갱신 실패:', error);
        return false;
    }
}

// 토큰 상태 확인 함수
async function checkTokenStatus() {
    try {
        const response = await fetch('/api/token-status', {
            credentials: 'include'
        });
        
        if (response.ok) {
            const status = await response.json();
            return status;
        }
        return null;
    } catch (error) {
        console.error('토큰 상태 확인 실패:', error);
        return null;
    }
}

// 토큰 만료 체크 및 자동 갱신
async function checkAndRefreshToken() {
    const status = await checkTokenStatus();
    
    if (status) {
        // 액세스 토큰이 만료되었고 리프레시 토큰이 유효한 경우
        if (status.access_token?.expired && status.refresh_token?.exists && !status.refresh_token?.expired) {
            console.log('액세스 토큰이 만료되었습니다. 자동 갱신을 시도합니다...');
            const refreshed = await refreshAccessToken();
            if (!refreshed) {
                // 갱신 실패 시 로그인 페이지로 이동
                showNotification('세션이 만료되었습니다. 다시 로그인해주세요.', 'warning');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
                return false;
            }
        }
        // 리프레시 토큰도 만료된 경우
        else if (status.refresh_token?.expired) {
            showNotification('로그인 세션이 만료되었습니다. 다시 로그인해주세요.', 'warning');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
            return false;
        }
    }
    
    return true;
}

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
            // 토큰 만료 시 자동 갱신 시도
            console.log('API 요청 중 토큰 만료 감지. 자동 갱신을 시도합니다...');
            const refreshed = await refreshAccessToken();
            
            if (refreshed) {
                // 토큰 갱신 성공 시 원래 요청 재시도
                const newToken = localStorage.getItem('access_token');
                const retryOptions = {
                    ...options,
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${newToken}`
                    }
                };
                
                const retryResponse = await fetch(url, retryOptions);
                return retryResponse;
            } else {
                // 토큰 갱신 실패 시 로그인 페이지로 이동
                showNotification('인증이 만료되었습니다. 다시 로그인해주세요.', 'warning');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
                return null;
            }
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

    try {
        const response = await fetch('/api/user/me', {
            credentials: 'include'
        });
        
        
        if (response.ok) {
            const user = await response.json();

            const adminMenuItem = document.getElementById('admin-menu-item');
            
            if (user.is_admin && adminMenuItem) {
                adminMenuItem.style.display = 'block';

            }
        } else {

        }
    } catch (error) {

    }
}

// 토큰 상태를 화면에 표시하는 함수
function updateTokenStatusDisplay(status) {
    const tokenExpiryElement = document.getElementById('token-expiry');
    if (!tokenExpiryElement) return;
    
    if (!status || (!status.access_token?.exists && !status.refresh_token?.exists)) {
        tokenExpiryElement.innerHTML = '<span class="text-danger">인증되지 않음</span>';
        return;
    }
    
    let statusText = '';
    let statusClass = '';
    
    if (status.access_token?.exists && !status.access_token?.expired) {
        // 액세스 토큰이 유효한 경우
        const expiryTime = new Date(status.access_token.expiry_time);
        const now = new Date();
        const timeLeft = expiryTime - now;
        const hoursLeft = Math.floor(timeLeft / (1000 * 60 * 60));
        const minutesLeft = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
        
        if (hoursLeft > 0) {
            statusText = `${hoursLeft}시간 ${minutesLeft}분 남음`;
        } else {
            statusText = `${minutesLeft}분 남음`;
        }
        
        if (timeLeft < 1000 * 60 * 60) { // 1시간 미만
            statusClass = 'text-warning';
        } else {
            statusClass = 'text-success';
        }
    } else if (status.refresh_token?.exists && !status.refresh_token?.expired) {
        // 액세스 토큰은 만료되었지만 리프레시 토큰이 유효한 경우
        statusText = '토큰 갱신 필요';
        statusClass = 'text-warning';
    } else {
        // 모든 토큰이 만료된 경우
        statusText = '세션 만료';
        statusClass = 'text-danger';
    }
    
    tokenExpiryElement.innerHTML = `<span class="${statusClass}">${statusText}</span>`;
}

// 토큰 상태 확인 및 화면 업데이트
async function checkAndUpdateTokenStatus() {
    const status = await checkTokenStatus();
    updateTokenStatusDisplay(status);
    return status;
}

// 페이지 로드 시 토큰 상태 확인
document.addEventListener('DOMContentLoaded', async function() {
    // 로그인 페이지가 아닌 경우에만 토큰 상태 확인
    if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
        await checkAndUpdateTokenStatus();
    }
});

// 주기적으로 토큰 상태 확인 및 화면 업데이트 (5분마다)
setInterval(async function() {
    if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
        await checkAndUpdateTokenStatus();
    }
}, 5 * 60 * 1000); // 5분

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    
    // 쿠키 기반 인증이므로 localStorage 토큰 체크 제거
    // 서버에서 쿠키를 통해 인증을 처리함
    
    // 관리자 메뉴 표시 확인
    if (!window.location.pathname.includes('/login') && 
        !window.location.pathname.includes('/register') && 
        window.location.pathname !== '/') {
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
