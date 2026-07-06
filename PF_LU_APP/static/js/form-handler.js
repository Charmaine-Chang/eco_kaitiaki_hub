/**
 * form-handler.js
 * Centralized form validation and interaction safety logic.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 0. Auto-inject novalidate and needs-validation to POST forms to enforce custom Bootstrap validation globally
    const postForms = document.querySelectorAll('form[method="POST"]:not(.no-auto-validate)');
    postForms.forEach(form => {
        form.setAttribute('novalidate', '');
        form.classList.add('needs-validation');
    });

    // 1. Fetch all the forms we want to apply custom Bootstrap validation styles to
    const forms = document.querySelectorAll('.needs-validation');

    // 2. Add Bootstrap validation listeners to explicitly marked forms
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // 3. Global Submit Button State Management (Anti-Double-Submission)
    // We attach to all forms that do not have the 'no-auto-disable' class.
    const allForms = document.querySelectorAll('form:not(.no-auto-disable)');
    Array.from(allForms).forEach(form => {
        form.addEventListener('submit', function (event) {
            // Only proceed if form is valid according to native validation
            // If it's not valid, the browser will block submission anyway (unless novalidate is set)
            if (form.checkValidity()) {
                // Find submit buttons
                const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
                
                submitButtons.forEach(btn => {
                    // Prevent modifying buttons that are already disabled or shouldn't be touched
                    if (!btn.disabled && !btn.classList.contains('no-auto-disable')) {
                        // We use a small timeout to ensure the form actually submits before disabling
                        // because disabling immediately can sometimes prevent the submit action in older browsers/edge cases.
                        setTimeout(() => {
                            btn.disabled = true;
                            // Add a spinner
                            const originalText = btn.innerHTML;
                            btn.setAttribute('data-original-text', originalText);
                            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...`;
                            btn.classList.add('opacity-75');
                        }, 10);
                    }
                });
            }
        });
    });
});
