'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

type Manifest = {
  model: { uri: string };
  rooms: Array<{ id: string; name: string; position: [number, number, number] }>;
  issues: Array<{ id: string; position: [number, number, number]; tone: string }>;
  fixtures: Array<{ id: string; type: string; discipline: string; position: [number, number, number] }>;
};

function materialForFixture(discipline:string){
  const colors:Record<string,string>={architectural:'#88a895',electrical:'#5f86bd',mechanical:'#d18a43'};
  return new THREE.MeshStandardMaterial({color:colors[discipline]||'#8da097',roughness:.64,metalness:.05});
}

function addFixtureVisual(scene:THREE.Scene,fixture:Manifest['fixtures'][number]){
  const group=new THREE.Group();
  group.name=`fixture_${fixture.id}`;
  group.position.set(...fixture.position);
  const material=materialForFixture(fixture.discipline);
  const addBox=(size:[number,number,number],offset:[number,number,number]=[0,0,0])=>{
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),material);
    mesh.position.set(...offset);mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);return mesh;
  };
  if(fixture.type==='ceiling_light'){
    const mesh=new THREE.Mesh(new THREE.CylinderGeometry(.19,.19,.055,24),new THREE.MeshStandardMaterial({color:'#f5f0d9',emissive:'#fff3b3',emissiveIntensity:.32,roughness:.45}));
    group.add(mesh);
  }else if(['ceiling_diffuser','ceiling_return'].includes(fixture.type)){
    addBox(fixture.type==='ceiling_return'?[.48,.055,.72]:[.44,.055,.44]);
    for(let line=-.12;line<=.12;line+=.08)addBox([.34,.012,.012],[0,.035,line]);
  }else if(fixture.type==='electrical_panel'){
    addBox([.42,.78,.14]);addBox([.34,.6,.025],[0,0,.082]);
  }else if(fixture.type==='receptacle'){
    addBox([.18,.28,.055]);
    const slotMaterial=new THREE.MeshBasicMaterial({color:'#e9f0ec'});
    for(const x of [-.035,.035]){const slot=new THREE.Mesh(new THREE.BoxGeometry(.018,.06,.008),slotMaterial);slot.position.set(x,.035,.032);group.add(slot)}
  }else if(fixture.type==='mechanical_equipment'){
    addBox([.9,1.35,.72],[0,.05,0]);
    for(let y=-.4;y<=.4;y+=.16)addBox([.68,.025,.018],[0,y,.37]);
  }else if(fixture.type==='sink'){
    addBox([.82,.08,.52]);
    const basin=new THREE.Mesh(new THREE.TorusGeometry(.18,.028,10,24),material);basin.rotation.x=Math.PI/2;basin.position.y=.06;group.add(basin);
  }else if(fixture.type==='casework'||fixture.type==='vanity'){
    addBox(fixture.type==='casework'?[1.25,.85,.58]:[.85,.82,.52],[0,.02,0]);
    addBox(fixture.type==='casework'?[1.3,.045,.62]:[.9,.045,.56],[0,.47,0]);
  }else addBox([.42,.32,.42]);
  scene.add(group);
}

export function ThreeSpatialScene({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (id: string) => void;
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  const onSelectRef = useRef(onSelect);
  const [status, setStatus] = useState('Loading coordinated model…');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    const root = mountRef.current;
    if (!root) return;
    let disposed = false;
    let frame = 0;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#f5f7f6');
    scene.fog = new THREE.Fog('#f5f7f6', 24, 48);

    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 120);
    camera.position.set(18.5, 15.5, 19.5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.04;
    renderer.shadowMap.enabled = true;
    renderer.domElement.className = 'three-spatial-canvas';
    renderer.domElement.setAttribute('aria-label', 'Interactive coordinated 3D construction model');
    root.appendChild(renderer.domElement);

    const labels = new CSS2DRenderer();
    labels.domElement.className = 'three-spatial-labels';
    labels.domElement.style.position = 'absolute';
    labels.domElement.style.inset = '0';
    labels.domElement.style.pointerEvents = 'none';
    root.appendChild(labels.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.target.set(7.5, 0.85, 5.0);
    controls.minDistance = 10;
    controls.maxDistance = 38;
    controls.maxPolarAngle = Math.PI * 0.47;

    scene.add(new THREE.HemisphereLight('#ffffff', '#ccd6d0', 2.2));
    const sun = new THREE.DirectionalLight('#ffffff', 2.8);
    sun.position.set(8, 18, 4);
    sun.castShadow = true;
    scene.add(sun);

    const grid = new THREE.GridHelper(22, 22, '#9ba9a1', '#d5ddd8');
    grid.position.set(7.5, -0.065, 5);
    const gridMaterials = Array.isArray(grid.material) ? grid.material : [grid.material];
    gridMaterials.forEach((material) => {
      material.opacity = 0.42;
      material.transparent = true;
    });
    scene.add(grid);

    const loader = new GLTFLoader();
    fetch('/demo/drawing-set.json', { cache: 'force-cache' })
      .then((response) => {
        if (!response.ok) throw new Error('Drawing-set manifest could not be loaded');
        return response.json() as Promise<Manifest>;
      })
      .then((manifest) => {
        if (disposed) return;
        loader.load(
          manifest.model.uri,
          (gltf) => {
            if (disposed) return;
            gltf.scene.traverse((child) => {
              if (!(child instanceof THREE.Mesh)) return;
              child.geometry.computeVertexNormals();
              child.castShadow = true;
              child.receiveShadow = true;
              const name = child.name.toLowerCase();
              if (name.includes('fixture')) {
                child.visible = false;
                return;
              }
              if (name.includes('wall')) {
                child.material = new THREE.MeshBasicMaterial({
                  color: '#cfd8d3',
                  transparent: true,
                  opacity: 0.42,
                  side: THREE.DoubleSide,
                  depthWrite: false,
                });
              } else if (name.includes('floor')) {
                child.material = new THREE.MeshBasicMaterial({ color: '#f7f8f6', side: THREE.DoubleSide });
              } else {
                child.material = new THREE.MeshBasicMaterial({ color: '#c79745', side: THREE.DoubleSide });
              }
              const edges = new THREE.LineSegments(
                new THREE.EdgesGeometry(child.geometry, 22),
                new THREE.LineBasicMaterial({ color: '#3d4a43', transparent: true, opacity: name.includes('wall') ? 0.58 : 0.32 }),
              );
              child.add(edges);
            });
            scene.add(gltf.scene);

            (manifest.fixtures||[]).forEach((fixture)=>addFixtureVisual(scene,fixture));

            manifest.rooms.forEach((room) => {
              const element = document.createElement('span');
              element.className = 'three-room-label';
              element.textContent = room.name.toUpperCase();
              const label = new CSS2DObject(element);
              label.position.set(...room.position);
              scene.add(label);
            });
            manifest.issues.forEach((issue) => {
              const color = issue.tone === 'critical' ? '#d44a43' : issue.tone === 'warning' ? '#c58a28' : '#3f72c8';
              const marker = new THREE.Group();
              marker.position.set(...issue.position);
              const stem = new THREE.Mesh(
                new THREE.CylinderGeometry(0.018, 0.018, 0.72, 10),
                new THREE.MeshBasicMaterial({ color }),
              );
              stem.position.y = -0.36;
              marker.add(stem);
              marker.add(new THREE.Mesh(new THREE.SphereGeometry(0.13, 18, 12), new THREE.MeshBasicMaterial({ color })));
              const button = document.createElement('button');
              button.type = 'button';
              button.dataset.issue = issue.id;
              button.className = `three-issue-label three-issue-label--${issue.tone}`;
              button.textContent = issue.id;
              button.style.pointerEvents = 'auto';
              button.onclick = () => onSelectRef.current(issue.id);
              const label = new CSS2DObject(button);
              label.position.set(0, 0.28, 0);
              marker.add(label);
              scene.add(marker);
            });
            setStatus('Coordinated A/E/M model · drag to orbit');
          },
          undefined,
          () => {
            setFailed(true);
            setStatus('The coordinated GLB could not be loaded.');
          },
        );
      })
      .catch(() => {
        setFailed(true);
        setStatus('The drawing-set manifest could not be loaded.');
      });

    const resize = () => {
      const width = Math.max(1, root.clientWidth);
      const height = Math.max(1, root.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      labels.setSize(width, height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(root);
    resize();

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      labels.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      scene.traverse((child) => {
        if (!(child instanceof THREE.Mesh || child instanceof THREE.LineSegments)) return;
        child.geometry.dispose();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((material) => material.dispose());
      });
      renderer.dispose();
      labels.domElement.remove();
      renderer.domElement.remove();
    };
  }, []);

  useEffect(() => {
    const root = mountRef.current;
    root?.querySelectorAll<HTMLButtonElement>('.three-issue-label').forEach((label) => {
      label.classList.toggle('selected', label.dataset.issue === selected);
    });
  }, [selected, status]);

  return (
    <div className={`three-spatial-root ${failed ? 'three-spatial-root--failed' : ''}`} ref={mountRef}>
      <div className="three-scene-status">{status}</div>
      <div className="three-scene-legend" aria-label="Model object legend">
        <span><i className="three-scene-key three-scene-key--architectural" />Architectural fixtures</span>
        <span><i className="three-scene-key three-scene-key--electrical" />Electrical devices</span>
        <span><i className="three-scene-key three-scene-key--mechanical" />Mechanical equipment</span>
      </div>
    </div>
  );
}
