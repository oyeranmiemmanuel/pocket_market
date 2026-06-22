// ===================== GLOBAL JS FOR TOP TECH APP =====================

document.addEventListener("DOMContentLoaded", () => {
    initMobileMenu();
    initSmoothScroll();
    initScrollAnimations();
    initImageModals();
    initWhatsAppButton();
    initContactFormAJAX();
    initActiveNavLinks();
    initBuyNowButtons();
});

// ===================== MOBILE MENU =====================
function openNav() {
  document.getElementById("mySidebar").style.width = "250px";
  document.getElementById("main").style.marginLeft = "250px";
}

function closeNav() {
  document.getElementById("mySidebar").style.width = "0";
  document.getElementById("main").style.marginLeft= "0";
}
// ===================== SMOOTH SCROLL =====================
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) target.scrollIntoView({ behavior: 'smooth' });
        });
    });
}

// ===================== SCROLL ANIMATIONS =====================
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('show');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.service-card, .brand-card, .teaser-card, .product-card').forEach(el => {
        el.classList.add('hidden');
        observer.observe(el);
    });
}

// ===================== IMAGE MODAL =====================
function initImageModals() {
    const images = document.querySelectorAll('.brand-card img, .teaser-card img, .product-card img');

    const modal = document.createElement('div');
    modal.className = 'image-modal';
    modal.innerHTML = `
        <span class="close-modal">×</span>
        <img class="modal-image" src="" alt="">
    `;
    document.body.appendChild(modal);

    const modalImg = modal.querySelector('.modal-image');
    const closeBtn = modal.querySelector('.close-modal');

    images.forEach(img => {
        img.style.cursor = 'pointer';
        img.addEventListener('click', () => {
            modalImg.src = img.src;
            modal.style.display = 'flex';
        });
    });

    closeBtn.addEventListener('click', () => modal.style.display = 'none');
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.style.display = 'none';
    });
}

// ===================== WHATSAPP FLOATING BUTTON =====================
function initWhatsAppButton() {
    const waBtn = document.querySelector('.whatsapp-float');
    if (waBtn) {
        waBtn.addEventListener('click', () => {
            console.log('%cWhatsApp Button Clicked', 'color: #25D366; font-weight: bold');
        });
    }
}

// ===================== ACTIVE NAV LINKS =====================
function initActiveNavLinks() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-links a').forEach(link => {
        if (link.getAttribute('href') === currentPath || 
            window.location.href.includes(link.getAttribute('href'))) {
            link.classList.add('active-link');
        }
    });
}

// ===================== BUY NOW BUTTON =====================
function initBuyNowButtons() {
    document.querySelectorAll('.buy-now-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const productName = this.dataset.productName || "this product";
            const productPrice = this.dataset.price || "";

            const confirmBuy = confirm(`Buy ${productName} for ₦${productPrice}?\n\nProceed to checkout?`);

            if (confirmBuy) {
                // You can redirect to payment or cart later
                window.location.href = "{% url 'initialize_payment' %}"; 
                // Or show a better modal in future
            }
        });
    });
}

// ===================== AJAX CONTACT FORM =====================
function initContactFormAJAX() {
    const contactForm = document.getElementById('contactForm');
    if (!contactForm) return;

    contactForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = new FormData(this);
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;

        submitBtn.textContent = 'Sending...';
        submitBtn.disabled = true;

        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            const successMsg = document.createElement('div');
            successMsg.className = 'alert alert-success';
            successMsg.textContent = '✅ Message sent successfully! Nicholas will reply soon.';
            contactForm.prepend(successMsg);

            contactForm.reset();

        } catch (error) {
            const errorMsg = document.createElement('div');
            errorMsg.className = 'alert alert-error';
            errorMsg.textContent = '❌ Failed to send message. Please try again.';
            contactForm.prepend(errorMsg);
        } finally {
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    });
}

// ===================== UTILITIES =====================
function throttle(func, limit) {
    let inThrottle;
    return function() {
        if (!inThrottle) {
            func.apply(this, arguments);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Navbar scroll effect
window.addEventListener('scroll', throttle(() => {
    const nav = document.querySelector('nav');
    if (nav) {
        nav.classList.toggle('scrolled', window.scrollY > 100);
    }
}, 100));