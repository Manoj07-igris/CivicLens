/**
 * CivicLens Controlled Demo Portal - Client Script
 * Self-contained logic for multi-step educational simulation.
 */

(function () {
  'use strict';

  let currentStep = 1;
  const totalSteps = 5;
  let currentLang = 'en';

  const I18N = {
    en: {
      portal_title: "Income Certificate Application (Educational Demo)",
      portal_subtitle: "Revenue & Disaster Management Department Simulation",
      step1: "Applicant",
      step2: "Address",
      step3: "Income",
      step4: "Purpose",
      step5: "Review",
      step1_heading: "Step 1: Applicant Details (Fictional Data)",
      step1_desc: "Provide demo applicant identity details. Real names or identifiers are blocked.",
      lbl_applicant_name: "Applicant Full Name *",
      hint_applicant_name: "Include initial and fictional suffix",
      lbl_parent_name: "Parent / Spouse Name *",
      hint_parent_name: "Father, mother, or legal guardian",
      lbl_gender: "Gender *",
      lbl_dob: "Date of Birth *",
      step2_heading: "Step 2: Address & Jurisdiction",
      step2_desc: "Enter the applicant's demo residential address for jurisdictional verification.",
      lbl_door_street: "Door No. & Street *",
      lbl_taluk: "Taluk *",
      lbl_district: "District *",
      lbl_pincode: "Postal PIN Code *",
      step3_heading: "Step 3: Income & Occupation Declaration",
      step3_desc: "Declare annual family income and occupational source for eligibility assessment.",
      lbl_occupation: "Primary Occupation *",
      lbl_annual_income: "Annual Family Income (INR) *",
      hint_annual_income: "Total combined annual income",
      lbl_source_income: "Primary Income Source Details *",
      step4_heading: "Step 4: Purpose of Application",
      step4_desc: "Select the intended use case for the income certificate.",
      lbl_purpose: "Purpose of Certificate *",
      lbl_remarks: "Additional Remarks (Optional)",
      step5_heading: "Step 5: Review & Confirmation",
      step5_desc: "Review the entered details before recording this demo application submission.",
      tbl_field: "Field",
      tbl_value: "Entered Value",
      lbl_confirm_demo: "I confirm that all entered details are fictional demo data for educational purposes.",
      btn_back: "← Back",
      btn_sample: "Fill Sample Data",
      btn_next: "Continue →",
      btn_submit: "Submit Demo Application"
    },
    ta: {
      portal_title: "வருமானச் சான்றிதழ் விண்ணப்பம் (கல்வி மாதிரி வலைவாசல்)",
      portal_subtitle: "வருவாய் மற்றும் பேரிடர் மேலாண்மைத் துறை மாதிரி உருவகப்படுத்துதல்",
      step1: "விண்ணப்பதாரர்",
      step2: "முகவரி",
      step3: "வருமானம்",
      step4: "நோக்கம்",
      step5: "சரிபார்த்தல்",
      step1_heading: "படி 1: விண்ணப்பதாரர் விவரங்கள் (மாதிரி தரவு)",
      step1_desc: "மாதிரி விண்ணப்பதாரர் அடையாள விவரங்களை உள்ளிடவும். உண்மையான தனிநபர் அடையாளங்கள் தடுக்கப்படும்.",
      lbl_applicant_name: "விண்ணப்பதாரர் முழுப் பெயர் *",
      hint_applicant_name: "முழுப் பெயர் மற்றும் மாதிரி முன்னொட்டு",
      lbl_parent_name: "பெற்றோர் / கணவர் பெயர் *",
      hint_parent_name: "தந்தை, தாய் அல்லது சட்டப்பூர்வ பாதுகாவலர்",
      lbl_gender: "பாலினம் *",
      lbl_dob: "பிறந்த தேதி *",
      step2_heading: "படி 2: முகவரி மற்றும் அதிகார வரம்பு",
      step2_desc: "அதிகார வரம்பை சரிபார்க்க விண்ணப்பதாரரின் மாதிரி குடியிருப்பு முகவரியை உள்ளிடவும்.",
      lbl_door_street: "கதவு எண் மற்றும் தெரு *",
      lbl_taluk: "வட்டம் *",
      lbl_district: "மாவட்டம் *",
      lbl_pincode: "அஞ்சல் குறியீட்டு எண் *",
      step3_heading: "படி 3: வருமானம் மற்றும் தொழில் அறிவிப்பு",
      step3_desc: "தகுதி மதிப்பீட்டிற்கு குடும்ப ஆண்டு வருமானம் மற்றும் தொழில் ஆதாரத்தை அறிவிக்கவும்.",
      lbl_occupation: "முதன்மை தொழில் *",
      lbl_annual_income: "குடும்ப ஆண்டு வருமானம் (ரூ.) *",
      hint_annual_income: "அனைத்து வழிகளிலிருந்தும் கிடைக்கும் மொத்த ஆண்டு வருமானம்",
      lbl_source_income: "வருமான ஆதாரம் விளக்கம் *",
      step4_heading: "படி 4: சான்றிதழின் நோக்கம்",
      step4_desc: "வருமானச் சான்றிதழ் தேவைப்படும் காரணத்தைத் தேர்ந்தெடுக்கவும்.",
      lbl_purpose: "சான்றிதழின் நோக்கம் *",
      lbl_remarks: "கூடுதல் குறிப்புகள் (தேவையெனில்)",
      step5_heading: "படி 5: சரிபார்த்தல் மற்றும் உறுதிப்படுத்தல்",
      step5_desc: "மாதிரி விண்ணப்பத்தைச் சமர்ப்பிக்கும் முன் தகவல்களைச் சரிபார்க்கவும்.",
      tbl_field: "புலம்",
      tbl_value: "உள்ளிட்ட மதிப்பு",
      lbl_confirm_demo: "அனைத்து விவரங்களும் கல்வி நோக்கத்திற்கான மாதிரி விவரங்கள் மட்டுமே என்பதை உறுதிப்படுத்துகிறேன்.",
      btn_back: "← பின்செல்",
      btn_sample: "மாதிரி தரவை நிரப்பு",
      btn_next: "தொடர்க →",
      btn_submit: "மாதிரி விண்ணப்பத்தைச் சமர்ப்பி"
    }
  };

  const SAMPLE_DATA = {
    applicant_name: "K. Ananya (Demo)",
    parent_guardian_name: "M. Kumar (Demo)",
    gender: "female",
    dob: "1995-06-15",
    door_and_street: "12, Gandhi Street (Demo)",
    taluk: "Mylapore",
    district: "Chennai (Demo)",
    pincode: "600004",
    occupation: "Self-employed",
    annual_income: "72000",
    source_of_income: "Tailoring & Handicrafts (Demo)",
    purpose: "Higher Education Scholarship",
    remarks: "Applying for college merit scholarship (Demo)"
  };

  function getQueryParam(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
  }

  function setLanguage(lang) {
    currentLang = lang === 'ta' ? 'ta' : 'en';
    const dict = I18N[currentLang];
    
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (dict[key]) {
        el.textContent = dict[key];
      }
    });

    const enBtn = document.getElementById('lang-en-btn');
    const taBtn = document.getElementById('lang-ta-btn');
    if (enBtn && taBtn) {
      enBtn.classList.toggle('active', currentLang === 'en');
      taBtn.classList.toggle('active', currentLang === 'ta');
    }

    const titleEl = document.getElementById('portal-title');
    const subTitleEl = document.getElementById('portal-subtitle');
    if (titleEl) titleEl.textContent = dict.portal_title;
    if (subTitleEl) subTitleEl.textContent = dict.portal_subtitle;
  }

  function showAlert(msg, isError = true) {
    const box = document.getElementById('alert-box');
    if (!box) return;
    box.textContent = msg;
    box.className = 'alert-box ' + (isError ? 'alert-error' : 'alert-info');
    box.classList.remove('hidden');
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function clearAlert() {
    const box = document.getElementById('alert-box');
    if (box) box.classList.add('hidden');
  }

  function getFormData() {
    const data = {};
    const inputs = document.querySelectorAll('#demo-form [data-field]');
    inputs.forEach(input => {
      const field = input.getAttribute('data-field');
      if (input.type === 'checkbox') {
        data[field] = input.checked;
      } else {
        data[field] = input.value ? input.value.trim() : '';
      }
    });
    return data;
  }

  function fillSampleData() {
    Object.entries(SAMPLE_DATA).forEach(([field, val]) => {
      const el = document.querySelector(`[data-field="${field}"]`);
      if (el) {
        el.value = val;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    clearAlert();
  }

  function validateStep(step) {
    clearAlert();
    const currentPanel = document.getElementById(`step-panel-${step}`);
    if (!currentPanel) return true;

    const requiredFields = currentPanel.querySelectorAll('[data-field][required]');
    for (const field of requiredFields) {
      if (field.type === 'checkbox') {
        if (!field.checked) {
          showAlert(currentLang === 'ta' ? 'தொடர உறுதிப்படுத்தல் பெட்டியைத் தேர்ந்தெடுக்கவும்.' : 'Please check the confirmation box to proceed.');
          field.focus();
          return false;
        }
      } else if (!field.value || !field.value.trim()) {
        showAlert(currentLang === 'ta' ? 'அனைத்து கட்டாயப் புலங்களையும் நிரப்பவும்.' : 'Please fill all required fields before proceeding.');
        field.focus();
        return false;
      }
    }

    if (step === 2) {
      const pincode = document.getElementById('pincode');
      if (pincode && pincode.value && !/^\d{6}$/.test(pincode.value.trim())) {
        showAlert(currentLang === 'ta' ? 'செல்லுபடியாகும் 6-இலக்க அஞ்சல் குறியீட்டை உள்ளிடவும்.' : 'Please enter a valid 6-digit postal PIN code.');
        pincode.focus();
        return false;
      }
    }

    if (step === 3) {
      const inc = document.getElementById('annual_income');
      if (inc && (Number(inc.value) < 1000 || isNaN(Number(inc.value)))) {
        showAlert(currentLang === 'ta' ? 'செல்லுபடியாகும் ஆண்டு வருமானத்தை உள்ளிடவும்.' : 'Please enter a valid annual income.');
        inc.focus();
        return false;
      }
    }

    return true;
  }

  function renderReviewTable() {
    const tbody = document.getElementById('review-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    const labels = {
      applicant_name: { en: "Applicant Full Name", ta: "விண்ணப்பதாரர் பெயர்" },
      parent_guardian_name: { en: "Parent / Spouse Name", ta: "பெற்றோர் / கணவர் பெயர்" },
      gender: { en: "Gender", ta: "பாலினம்" },
      dob: { en: "Date of Birth", ta: "பிறந்த தேதி" },
      door_and_street: { en: "Door & Street", ta: "கதவு & தெரு" },
      taluk: { en: "Taluk", ta: "வட்டம்" },
      district: { en: "District", ta: "மாவட்டம்" },
      pincode: { en: "PIN Code", ta: "அஞ்சல் குறியீடு" },
      occupation: { en: "Occupation", ta: "தொழில்" },
      annual_income: { en: "Annual Income (INR)", ta: "ஆண்டு வருமானம் (ரூ.)" },
      source_of_income: { en: "Income Source", ta: "வருமான ஆதாரம்" },
      purpose: { en: "Application Purpose", ta: "விண்ணப்ப நோக்கம்" },
      remarks: { en: "Remarks", ta: "குறிப்புகள்" }
    };

    const data = getFormData();
    Object.entries(labels).forEach(([fieldKey, labelObj]) => {
      const tr = document.createElement('tr');
      const tdLabel = document.createElement('td');
      tdLabel.textContent = labelObj[currentLang] || labelObj.en;
      tdLabel.style.fontWeight = '600';

      const tdVal = document.createElement('td');
      let val = data[fieldKey] || '—';
      if (fieldKey === 'annual_income' && data[fieldKey]) {
        val = '₹' + Number(data[fieldKey]).toLocaleString('en-IN');
      }
      tdVal.textContent = val;

      tr.appendChild(tdLabel);
      tr.appendChild(tdVal);
      tbody.appendChild(tr);
    });
  }

  function goToStep(step) {
    if (step < 1 || step > totalSteps) return;

    for (let i = 1; i <= totalSteps; i++) {
      const panel = document.getElementById(`step-panel-${i}`);
      if (panel) panel.classList.toggle('hidden', i !== step);
    }

    document.querySelectorAll('.step-item').forEach(item => {
      const s = Number(item.getAttribute('data-step'));
      item.classList.toggle('active', s === step);
      item.classList.toggle('completed', s < step);
    });

    currentStep = step;

    const backBtn = document.getElementById('btn-back');
    const nextBtn = document.getElementById('btn-next');
    const submitBtn = document.getElementById('btn-submit');
    const sampleBtn = document.getElementById('btn-sample-fill');

    if (backBtn) backBtn.classList.toggle('hidden', step === 1);
    if (nextBtn) nextBtn.classList.toggle('hidden', step === totalSteps);
    if (submitBtn) submitBtn.classList.toggle('hidden', step !== totalSteps);
    if (sampleBtn) sampleBtn.classList.toggle('hidden', step === totalSteps);

    if (step === totalSteps) {
      renderReviewTable();
    }

    clearAlert();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    window.dispatchEvent(new CustomEvent('demo_step_changed', { detail: { step } }));
  }

  function generateDemoRef() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let code = '';
    for (let i = 0; i < 6; i++) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return `DEMO-IC-${code}`;
  }

  async function handleFormSubmit(e) {
    if (e) e.preventDefault();
    if (!validateStep(5)) return;

    const data = getFormData();
    const demoRef = generateDemoRef();
    const nowIso = new Date().toLocaleString();

    // Attempt to post to backend demo endpoint if available
    try {
      await fetch('/demo-portal/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data,
          fictional_confirmed: true,
          application_number: demoRef
        })
      });
    } catch (_) {
      // Offline / standalone browser preview fallback
    }

    // Hide form and display success card
    const form = document.getElementById('demo-form');
    const successCard = document.getElementById('submission-success');
    const stepper = document.querySelector('.step-indicator');

    if (form) form.classList.add('hidden');
    if (stepper) stepper.classList.add('hidden');
    if (successCard) {
      successCard.classList.remove('hidden');
      document.getElementById('receipt-ref').textContent = demoRef;
      document.getElementById('receipt-time').textContent = nowIso;
      document.getElementById('receipt-applicant').textContent = data.applicant_name || 'K. Ananya (Demo)';
    }

    window.dispatchEvent(new CustomEvent('demo_submitted', { detail: { ref: demoRef, data } }));
  }

  function init() {
    const langParam = getQueryParam('lang');
    if (langParam === 'ta') {
      setLanguage('ta');
    } else {
      setLanguage('en');
    }

    document.getElementById('lang-en-btn')?.addEventListener('click', () => setLanguage('en'));
    document.getElementById('lang-ta-btn')?.addEventListener('click', () => setLanguage('ta'));

    document.getElementById('btn-next')?.addEventListener('click', () => {
      if (validateStep(currentStep)) {
        goToStep(currentStep + 1);
      }
    });

    document.getElementById('btn-back')?.addEventListener('click', () => {
      goToStep(currentStep - 1);
    });

    document.getElementById('btn-sample-fill')?.addEventListener('click', () => {
      fillSampleData();
    });

    document.getElementById('btn-submit')?.addEventListener('click', handleFormSubmit);

    document.getElementById('btn-restart')?.addEventListener('click', () => {
      const form = document.getElementById('demo-form');
      const successCard = document.getElementById('submission-success');
      const stepper = document.querySelector('.step-indicator');
      if (form) {
        form.reset();
        form.classList.remove('hidden');
      }
      if (stepper) stepper.classList.remove('hidden');
      if (successCard) successCard.classList.add('hidden');
      goToStep(1);
    });

    // Expose helpers for Playwright testing / automation
    window.__DEMO_PORTAL__ = {
      getCurrentStep: () => currentStep,
      getFormData,
      goToStep,
      fillSampleData,
      validateStep,
      submit: handleFormSubmit
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
