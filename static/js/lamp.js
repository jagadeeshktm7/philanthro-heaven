/* Interactive Lamp & Pull Cord Mechanics */

document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    const lampSvg = document.getElementById('lampSvg');
    const pullGroup = document.getElementById('pullGroup');
    const cordLine = document.getElementById('cordLine');
    const cordBead = document.getElementById('cordBead');
    const fallbackBtn = document.getElementById('fallbackToggle');
    const soundToggleBtn = document.getElementById('soundToggleBtn');
    
    // Auth Tabs
    const tabSignIn = document.getElementById('tabSignIn');
    const tabSignUp = document.getElementById('tabSignUp');
    const panelSignIn = document.getElementById('panelSignIn');
    const panelSignUp = document.getElementById('panelSignUp');
    
    // Color Palette Buttons
    const colorBtns = document.querySelectorAll('.color-btn');

    let isLampOn = false;
    let isDragging = false;
    let startY = 0;
    let currentDragY = 0;
    const maxDrag = 60;
    const activationThreshold = 45;
    let soundEnabled = false;

    // Lighting color definitions
    const lightingColors = {
        amber: { primary: '#FFAB3D', glow: 'rgba(255, 171, 61, 0.35)', beam: 'rgba(255, 171, 61, 0.18)' },
        cyan: { primary: '#00F0FF', glow: 'rgba(0, 240, 255, 0.35)', beam: 'rgba(0, 240, 255, 0.18)' },
        rose: { primary: '#FF3385', glow: 'rgba(255, 51, 133, 0.35)', beam: 'rgba(255, 51, 133, 0.18)' },
        mint: { primary: '#00E676', glow: 'rgba(0, 230, 118, 0.35)', beam: 'rgba(0, 230, 118, 0.18)' },
        moonlight: { primary: '#D8E5FF', glow: 'rgba(216, 229, 255, 0.35)', beam: 'rgba(216, 229, 255, 0.18)' }
    };

    // Web Audio API Sound Synthesizer
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playSound(type) {
        if (!soundEnabled) return;
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === 'click') {
            osc.frequency.setValueAtTime(400, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(100, audioCtx.currentTime + 0.05);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.05);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.05);
        } else if (type === 'switchOn') {
            osc.frequency.setValueAtTime(600, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.1);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.1);
        } else if (type === 'switchOff') {
            osc.frequency.setValueAtTime(800, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(300, audioCtx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.1);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.1);
        }
    }

    // Toggle Lamp State
    function toggleLamp() {
        isLampOn = !isLampOn;
        if (isLampOn) {
            body.classList.add('lamp-on');
            playSound('switchOn');
            const tooltip = document.getElementById('lampTooltip');
            if (tooltip) tooltip.style.display = 'none';
        } else {
            body.classList.remove('lamp-on');
            playSound('switchOff');
        }
    }

    // Pull Cord Drag Interactions
    if (pullGroup) {
        const startDrag = (clientY) => {
            isDragging = true;
            startY = clientY;
        };

        const duringDrag = (clientY) => {
            if (!isDragging) return;
            const deltaY = clientY - startY;
            currentDragY = Math.max(0, Math.min(maxDrag, deltaY));
            
            // Update cord and bead position
            cordLine.setAttribute('y2', 200 + currentDragY);
            cordBead.setAttribute('cy', 200 + currentDragY);

            if (currentDragY >= activationThreshold) {
                // Trigger toggle once threshold reached during pull
            }
        };

        const endDrag = () => {
            if (!isDragging) return;
            isDragging = false;
            
            if (currentDragY >= activationThreshold) {
                toggleLamp();
            }

            // Spring back animation
            currentDragY = 0;
            cordLine.setAttribute('y2', 200);
            cordBead.setAttribute('cy', 200);
            playSound('click');
        };

        // Mouse Events
        pullGroup.addEventListener('mousedown', (e) => startDrag(e.clientY));
        window.addEventListener('mousemove', (e) => duringDrag(e.clientY));
        window.addEventListener('mouseup', endDrag);

        // Touch Events
        pullGroup.addEventListener('touchstart', (e) => startDrag(e.touches[0].clientY));
        window.addEventListener('touchmove', (e) => duringDrag(e.touches[0].clientY));
        window.addEventListener('touchend', endDrag);
    }

    // Fallback button toggle
    if (fallbackBtn) {
        fallbackBtn.addEventListener('click', toggleLamp);
    }

    // Sound toggle button
    if (soundToggleBtn) {
        soundToggleBtn.addEventListener('click', () => {
            soundEnabled = !soundEnabled;
            soundToggleBtn.innerHTML = soundEnabled ? '<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/></svg>' : '<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>';
            playSound('click');
        });
    }

    // Color Theme Switcher
    colorBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            colorBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const colorKey = btn.getAttribute('data-color');
            const theme = lightingColors[colorKey];
            
            if (theme) {
                document.documentElement.style.setProperty('--light-primary', theme.primary);
                document.documentElement.style.setProperty('--light-glow', theme.glow);
                document.documentElement.style.setProperty('--light-beam', theme.beam);
                playSound('click');
            }
        });
    });

    // Auth Tabs Switcher
    if (tabSignIn && tabSignUp && panelSignIn && panelSignUp) {
        tabSignIn.addEventListener('click', () => {
            tabSignIn.classList.add('active');
            tabSignUp.classList.remove('active');
            panelSignIn.classList.add('active');
            panelSignUp.classList.remove('active');
            playSound('click');
        });

        tabSignUp.addEventListener('click', () => {
            tabSignUp.classList.add('active');
            tabSignIn.classList.remove('active');
            panelSignUp.classList.add('active');
            panelSignIn.classList.remove('active');
            playSound('click');
        });
    }
});
