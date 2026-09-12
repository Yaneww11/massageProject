/* Site header behaviour: scroll state, desktop dropdown, profile menu,
   mobile full-screen overlay. */
(function () {
    'use strict';

    var header = document.getElementById('site-header');
    var overlay = document.getElementById('mobile-overlay');

    /* --- Compact + hide-on-scroll ----------------------------------------- */
    if (header) {
        var lastY = window.pageYOffset;
        var ticking = false;

        function onScroll() {
            var y = window.pageYOffset;

            header.classList.toggle('is-compact', y > 8);

            // Never hide while the mobile overlay is open, or near the top.
            if (overlay && overlay.classList.contains('is-open')) {
                header.classList.remove('is-hidden');
            } else if (y > lastY && y > 120) {
                header.classList.add('is-hidden');
            } else if (y < lastY) {
                header.classList.remove('is-hidden');
            }

            lastY = y;
            ticking = false;
        }

        window.addEventListener('scroll', function () {
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(onScroll);
            }
        }, { passive: true });
    }

    /* --- Desktop dropdown -------------------------------------------------- */
    var trigger = document.getElementById('primary-menu-trigger');
    var group = trigger && trigger.closest('.site-nav__group');

    function closeDropdown(returnFocus) {
        if (!group || !group.classList.contains('is-open')) return;
        group.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');
        // The panel is display:none when closed, so focus inside it would be lost.
        if (returnFocus) trigger.focus();
    }

    if (trigger && group) {
        trigger.addEventListener('click', function (e) {
            e.stopPropagation();
            if (group.classList.contains('is-open')) {
                closeDropdown(false);
                return;
            }
            group.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
            var first = group.querySelector('.site-nav__item');
            if (first) first.focus();
        });

        // Close once focus leaves the group entirely (tabbing off the last item).
        group.addEventListener('focusout', function (e) {
            if (!group.contains(e.relatedTarget)) closeDropdown(false);
        });

        document.addEventListener('click', function (e) {
            if (!group.contains(e.target)) closeDropdown(false);
        });
    }

    /* --- Profile menu ------------------------------------------------------ */
    var userToggle = document.getElementById('user-menu-toggle');
    var userMenu = document.getElementById('user-menu');

    if (userToggle && userMenu) {
        userToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            var open = userMenu.classList.toggle('user-menu--open');
            userToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });

        document.addEventListener('click', function (e) {
            if (!userMenu.contains(e.target)) {
                userMenu.classList.remove('user-menu--open');
                userToggle.setAttribute('aria-expanded', 'false');
            }
        });
    }

    /* --- Mobile overlay ---------------------------------------------------- */
    var openBtn = document.getElementById('mobile-menu-open');
    var closeBtn = document.getElementById('mobile-menu-close');

    function openOverlay() {
        if (!overlay) return;
        overlay.hidden = false;
        overlay.classList.add('is-open');
        document.body.style.overflow = 'hidden';
        if (openBtn) openBtn.setAttribute('aria-expanded', 'true');
        if (closeBtn) closeBtn.focus();
    }

    function closeOverlay() {
        if (!overlay) return;
        overlay.classList.remove('is-open');
        overlay.hidden = true;
        document.body.style.overflow = '';
        if (openBtn) {
            openBtn.setAttribute('aria-expanded', 'false');
            openBtn.focus();
        }
    }

    if (openBtn) openBtn.addEventListener('click', openOverlay);
    if (closeBtn) closeBtn.addEventListener('click', closeOverlay);

    if (overlay) {
        overlay.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                // Auth-modal triggers stay put; they open a dialog of their own.
                if (link.hasAttribute('data-auth-modal-trigger')) return;
                closeOverlay();
            });
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        closeDropdown(true);
        if (overlay && overlay.classList.contains('is-open')) closeOverlay();
    });

    /* --- Mobile submenu ---------------------------------------------------- */
    var subTrigger = document.getElementById('mobile-submenu-trigger');
    var submenu = document.getElementById('mobile-submenu');

    if (subTrigger && submenu) {
        subTrigger.addEventListener('click', function () {
            var open = subTrigger.getAttribute('aria-expanded') === 'true';
            subTrigger.setAttribute('aria-expanded', open ? 'false' : 'true');
            submenu.hidden = open;
        });
    }

    /* --- Current-section marking ------------------------------------------ */
    var path = window.location.pathname;
    var hash = window.location.hash;

    document.querySelectorAll('.site-nav__item, .mobile-overlay__sublink').forEach(function (link) {
        var url = new URL(link.href, window.location.origin);
        var matches = url.pathname === path && (url.hash ? url.hash === hash : !hash);
        if (matches) link.classList.add('is-active');
    });
})();
